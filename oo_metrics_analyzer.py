import ast
import os
import csv
import json
import collections
import sys

def get_loc(node):
    """安全地获取AST节点的代码行数(LOC)。"""
    if hasattr(node, 'end_lineno') and hasattr(node, 'lineno'):
        return node.end_lineno - node.lineno + 1
    return 1 # 回退方案（兼容极老的Python版本）

def calculate_cyclomatic_complexity(node):
    """计算AST节点的圈复杂度 (Cyclomatic Complexity)。"""
    complexity = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor,
                              ast.ExceptHandler, ast.With, ast.AsyncWith,
                              ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            # 逻辑运算 and / or 也会增加复杂度分支
            complexity += len(child.values) - 1
        elif hasattr(ast, 'match_case') and isinstance(child, ast.match_case):
            # 兼容 Python 3.10+ 的 match-case 语法
            complexity += 1
    return complexity

def analyze_project(directory):
    classes_info = {} 
    short_to_id = collections.defaultdict(list)
    
    # 步骤 1: 第一遍遍历解析所有文件，提取类、方法、和基本继承结构
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.endswith('.py'):
                continue
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    source = f.read()
                tree = ast.parse(source)
            except Exception as e:
                print(f"解析文件出错 {filepath}: {e}")
                continue
                
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # 使用 路径+类名 防止同名类冲突
                    class_id = f"{filepath}::{node.name}"
                    short_to_id[node.name].append(class_id)
                    
                    bases = []
                    for base in node.bases:
                        # 获取继承的基类名
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(base.attr)
                            
                    classes_info[class_id] = {
                        'name': node.name,
                        'filepath': filepath,
                        'bases': bases,
                        'loc': get_loc(node),
                        'methods': {},
                        'attributes': set(),
                        'node': node
                    }
                    
                    # 查找该类内部的方法 (包含异步方法)
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            classes_info[class_id]['methods'][child.name] = {
                                'name': child.name,
                                'loc': get_loc(child),
                                'cc': calculate_cyclomatic_complexity(child),
                                'accessed_attrs': set(),
                                'called_internal_methods': set(),
                                'called_external_methods': set(),
                                'node': child,
                                'callers': set()
                            }

    # 步骤 2: 分析方法体，寻找属性访问 (self.xxx) 和方法调用
    for class_id, c_info in classes_info.items():
        # 获取类级别定义的属性 (如 Class variables)
        for child in c_info['node'].body:
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        c_info['attributes'].add(target.id)
            elif isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    c_info['attributes'].add(child.target.id)

        # 遍历分析每一个方法
        for m_name, m_info in c_info['methods'].items():
            for m_node in ast.walk(m_info['node']):
                # 寻找形如 self.xxx 的属性访问
                if isinstance(m_node, ast.Attribute):
                    if isinstance(m_node.value, ast.Name) and m_node.value.id == 'self':
                        m_info['accessed_attrs'].add(m_node.attr)
                        
                # 寻找方法调用
                if isinstance(m_node, ast.Call):
                    if isinstance(m_node.func, ast.Attribute):
                        if isinstance(m_node.func.value, ast.Name) and m_node.func.value.id == 'self':
                            # 内部调用 self.method()
                            m_info['called_internal_methods'].add(m_node.func.attr)
                        else:
                            # 外部调用 obj.method()
                            m_info['called_external_methods'].add(m_node.func.attr)
                    elif isinstance(m_node.func, ast.Name):
                        # 外部调用 func()
                        m_info['called_external_methods'].add(m_node.func.id)

    # 区分内部方法调用和真正的属性访问 (由于此时拥有了类里所有的 method_names)
    for class_id, c_info in classes_info.items():
        method_names = set(c_info['methods'].keys())
        for m_name, m_info in c_info['methods'].items():
            real_attrs = set()
            for attr in m_info['accessed_attrs']:
                if attr in method_names:
                    m_info['called_internal_methods'].add(attr)
                else:
                    real_attrs.add(attr)
                    # 确保类属性池知道这个属性
                    c_info['attributes'].add(attr)
            m_info['accessed_attrs'] = real_attrs

    # 步骤 3: 计算类之间的依赖耦合 (Afferent/Efferent Coupling)
    efferent = collections.defaultdict(set)
    afferent = collections.defaultdict(set)

    for class_id, c_info in classes_info.items():
        # 在整个类中查找对其它类的引用
        for node in ast.walk(c_info['node']):
            if isinstance(node, ast.Name):
                target_name = node.id
                if target_name in short_to_id and target_name != c_info['name']:
                    for target_id in short_to_id[target_name]:
                        efferent[class_id].add(target_id)
                        afferent[target_id].add(class_id)
            elif isinstance(node, ast.Attribute):
                 target_name = node.attr
                 if target_name in short_to_id and target_name != c_info['name']:
                    for target_id in short_to_id[target_name]:
                        efferent[class_id].add(target_id)
                        afferent[target_id].add(class_id)
                        
        # 继承带来的强耦合
        for base in c_info['bases']:
            if base in short_to_id:
                for target_id in short_to_id[base]:
                    efferent[class_id].add(target_id)
                    afferent[target_id].add(class_id)

    # 步骤 4: 映射方法调用者 (用于 JSON 需求)
    for caller_id, caller_c_info in classes_info.items():
        for caller_m_name, caller_m_info in caller_c_info['methods'].items():
            for ext_m in caller_m_info['called_external_methods']:
                # 在AST静态分析中采取模糊匹配法：如果外部方法名在某个类中存在，将其标记为调用方。
                for target_id, target_c_info in classes_info.items():
                    if caller_id != target_id and ext_m in target_c_info['methods']:
                        target_c_info['methods'][ext_m]['callers'].add(caller_c_info['name'])

    # 步骤 5: 计算继承树深度 (DIT)
    dit_map = {}
    dit_visited = set()
    
    def get_dit(cid):
        """递归获取继承深度，对Python这种多继承机制采取最大深度"""
        if cid in dit_map:
            return dit_map[cid]
        if cid in dit_visited:
            return 1 # 防止非法循环继承导致死循环
        dit_visited.add(cid)
        
        base_dits = []
        has_external_base = False
        for base in classes_info[cid]['bases']:
            if base in short_to_id:
                for b_id in short_to_id[base]:
                    base_dits.append(get_dit(b_id))
            else:
                has_external_base = True # 继承自外部库(如Exception, object等)
        
        if not base_dits:
            depth = 2 if has_external_base else 1
        else:
            depth = max(1 + max(base_dits), 2 if has_external_base else 1)
            
        dit_map[cid] = depth
        return depth
        
    for cid in classes_info:
        get_dit(cid)

    # 步骤 6: 计算 LCOM_HS, TCC, LCC 并聚合所有结果
    results = []
    json_output = {}

    for cid, c_info in classes_info.items():
        c_name = c_info['name']
        m = len(c_info['methods'])
        a = len(c_info['attributes'])
        
        ca = len(afferent[cid])
        ce = len(efferent[cid])
        loc = c_info['loc']
        dit = dit_map[cid]
        wmc = sum(m_info['cc'] for m_info in c_info['methods'].values())
        
        # 1. 计算 Henderson-Sellers LCOM
        sum_mu = sum(len(m_info['accessed_attrs']) for m_info in c_info['methods'].values())
        if m < 2 or a == 0:
            lcom_hs = 0.0
        else:
            avg_access = sum_mu / a
            lcom_hs = (avg_access - m) / (1 - m)
            
        # 2. 计算 TCC & LCC
        tcc = 0.0
        lcc = 0.0
        if m >= 2:
            methods_list = list(c_info['methods'].values())
            m_count = len(methods_list)
            total_pairs = m_count * (m_count - 1) / 2
            
            # 构建方法的直接连接矩阵 (共享属性 或 内部方法相互调用)
            direct_edges = 0
            adj = [[False] * m_count for _ in range(m_count)]
            
            for i in range(m_count):
                for j in range(i + 1, m_count):
                    m1 = methods_list[i]
                    m2 = methods_list[j]
                    shared_attrs = m1['accessed_attrs'].intersection(m2['accessed_attrs'])
                    calls = (m2['name'] in m1['called_internal_methods']) or (m1['name'] in m2['called_internal_methods'])
                    
                    if shared_attrs or calls:
                        adj[i][j] = True
                        adj[j][i] = True
                        direct_edges += 1
                        
            tcc = direct_edges / total_pairs if total_pairs > 0 else 0.0
            
            # 使用 BFS 寻找连通分量计算 LCC 间接联系
            visited_nodes = [False] * m_count
            indirect_pairs = 0
            
            for i in range(m_count):
                if not visited_nodes[i]:
                    q = [i]
                    visited_nodes[i] = True
                    comp_size = 0
                    while q:
                        curr = q.pop(0)
                        comp_size += 1
                        for j in range(m_count):
                            if adj[curr][j] and not visited_nodes[j]:
                                visited_nodes[j] = True
                                q.append(j)
                    
                    # 某个连通子集内所有节点两两之间互通
                    if comp_size > 1:
                        indirect_pairs += (comp_size * (comp_size - 1)) / 2
                    
            lcc = indirect_pairs / total_pairs if total_pairs > 0 else 0.0

        results.append({
            'ClassName': c_name,
            'Ca': ca,
            'Ce': ce,
            'LCOM': lcom_hs,
            'TCC': tcc,
            'LCC': lcc,
            'DIT': dit,
            'CC': wmc,
            'LOC': loc,
            'NOA': a,
            'NOM': m
        })
        
        # 准备 JSON 输出结构，为防止不同文件中有同名类覆盖现象进行兼容
        json_key = c_name
        if json_key in json_output:
            json_key = f"{c_name} ({os.path.basename(c_info['filepath'])})"
            
        json_output[json_key] = {}
        for m_name, m_info in c_info['methods'].items():
            json_output[json_key][m_name] = {
                'LOC': m_info['loc'],
                'callers': list(m_info['callers'])
            }

    return results, json_output

def main():
    if len(sys.argv) < 3:
        print("用法: python analyze_metrics.py <要分析的Python项目目录路径> <输出文件路径>")
        sys.exit(1)
        
    project_dir = sys.argv[1]
    if not os.path.isdir(project_dir):
        print(f"错误: 目录 '{project_dir}' 不存在。")
        sys.exit(1)

    output_dir = sys.argv[2]
    if not os.path.isdir(output_dir):
        print(f"错误: 目录 '{output_dir}' 不存在。")
        sys.exit(1)
        
    print(f"正在分析目录: {project_dir} ...")
    csv_results, json_results = analyze_project(project_dir)
    
    # 写入 CSV 文件
    csv_file = os.path.join(output_dir, 'class_details.csv')
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ClassName', 'Ca', 'Ce', 'LCOM', 'TCC', 'LCC', 'DIT', 'CC', 'LOC', 'NOA', 'NOM']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in csv_results:
            writer.writerow(row)
            
    # 写入 JSON 文件
    json_file = os.path.join(output_dir, 'method_details.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(json_results, f, ensure_ascii=False, indent=4)
        
    print(f"✅ 分析完成！")
    print(f" - 类级别指标结果已保存至: {csv_file}")
    print(f" - 方法级别及其调用者信息已保存至: {json_file}")

if __name__ == "__main__":
    main()
