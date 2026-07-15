# GUSUExtra
This is supporting information for the article Avoiding God Agents: An Empirical Solution to Architecting Standalone Multi-agent Systems with Multi-aspect Agents.  It includes the procedure and code of collecting and processing metrics data from 18 representive MASs. It also includes the collected data. The 18 MASs are:

JADE	[JADE Official Site](https://jade.tilab.com/)

Jason	https://jason.sourceforge.net/

SPADE	[SPADE GitHub](https://github.com/javipalanca/spade)

MASON	[MASON GitHub](https://github.com/eclab/mason)

Mesa	[Mesa GitHub](https://github.com/projectmesa/mesa)

GAMA Platform	[GAMA Platform](https://gama-platform.org/)

μRTS	[microRTS GitHub](https://github.com/santiontanon/microrts)

C&C RedAlert	[C&C Red Alert](https://github.com/electronicarts/CnC_Remastered_Collection)

Spring RTS game engine	[Spring GitHub](https://github.com/spring/spring)

GUSU	https://github.com/drrobincroft/GUSUExtra

PettingZoo	[PettingZoo GitHub](https://github.com/Farama-Foundation/PettingZoo)

RLlib	[RLlib GitHub](https://github.com/ray-project/ray/tree/master/rllib)

Melting Pot	[Melting Pot GitHub](https://github.com/google-deepmind/meltingpot)

AutoGen	[Microsoft AutoGen GitHub](https://github.com/microsoft/autogen)

MetaGPT	[MetaGPT GitHub](https://github.com/geekan/MetaGPT)

CrewAI	[CrewAI Official Site](https://github.com/camel-ai/camel)

CAMEL-AI	[CAMEL GitHub](https://github.com/camel-ai/camel)

AgentScope	[AgentScope GitHub](https://github.com/agentscope-ai/agentscope)

According to the primary programming languages, there are 3 kinds of MASs: C++, Java and Python.

# For C++ projects
The processing steps are:

1 Use Cppdepend (2024.1.0.27 pro) to obtain all metrics built in the tool (check the option "Keep XML to build report").

2 Check if the output directory CppDependOut\XmlFilesUsedToBuildReport includes TypesMetrics.xml. If not, send the following code query, export the results into QueryResult.xls under CppDependOut, and rename it to QueryResult_Types.xls.
```
from t in Application.Types
where t != null
select new { t,t.NbTypesUsingMe, t.CyclomaticComplexity, 
t.DepthOfInheritance,t.NbTypesUsed, t.LCOM,t.LCOMHS,
t.NbFields,t.NbMethods,t.NbLinesOfCode}
```
  
3 Send the following code query, export the results into QueryResult.xls under CppDependOut, andrename it to QueryResult_Fields.xls.
```
from t in Application.Types
from m in t.ChildMethods
from f in m.FieldsUsed
where t != null
select new { t, m, f, t.ChildMethods}
```

4 Send the following code query, export the results into QueryResult.xls under CppDependOut, andrename it to QueryResult_Invokes.xls.
```
from t in Application.Types
from m in t.ChildMethods
from otherm in m.MethodsCalled
where m != null
select new { t, m, otherm.ParentType}
```

5 Send the following code query, export the results into QueryResult.xls under CppDependOut, andrename it to QueryResult_Methods.xls.
```
from m in Application.Methods
where m != null
select new { m.ParentType, m, m.NbLinesOfCode}
```

6 Use PMD/CPD to obtian code duplication, export the results into duplication.csv under CppDependOut.
```
D:\pmd-bin-7.25.0\bin\pmd.bat cpd-gui
```

7 Use Cloc or Sonargraph to count LOC.
```
D:\cloc\cloc-2.08.exe <Input source folder path>
```

8 Use Matlab script CalMetrics.mlx to calculate 'Afferent Coupling' 'Efferent Coupling'	'Instability'	'Lack of Cohesion of Methods'	'Tight Class Cohesion'	'Loose Class Cohesion'	'Cyclomatic Complexity'	'Depth Inheritance Tree'	'Class Length'	'Number of attributes/fields'	'Number of methods'	'Method/Function length'. See the paper for metrics.
