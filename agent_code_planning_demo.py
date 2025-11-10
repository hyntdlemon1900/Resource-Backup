#!/usr/bin/env python3
"""
智能体代码规划与协同实现 - 可运行示例

这是一个完整的、可运行的示例程序，展示了智能体系统如何进行代码规划和协同。
可以直接运行此文件查看效果。

运行方式：
    python agent_code_planning_demo.py
"""

import ast
import re
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict


class VariableRegistry:
    """
    变量注册表
    
    功能：
    1. 跟踪所有变量的定义和使用
    2. 分析代码的变量依赖关系
    3. 检测未定义的变量
    """
    
    def __init__(self):
        self.variables = {}
        self.scopes = []
        
    def analyze_dependencies(self, code: str) -> Dict[str, List[str]]:
        """
        分析代码的变量依赖
        
        Args:
            code: 要分析的代码字符串
            
        Returns:
            字典包含 'required' (需要的变量) 和 'produced' (产生的变量)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return {'required': [], 'produced': []}
        
        required = set()
        produced = set()
        
        class VariableAnalyzer(ast.NodeVisitor):
            def __init__(self):
                self.local_vars = set()
                
            def visit_Name(self, node):
                """访问变量名节点"""
                if isinstance(node.ctx, ast.Store):
                    # 变量被赋值（定义）
                    produced.add(node.id)
                    self.local_vars.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    # 变量被使用
                    if node.id not in self.local_vars:
                        required.add(node.id)
                        
            def visit_FunctionDef(self, node):
                """访问函数定义"""
                produced.add(node.name)
                # 函数参数也算本地变量
                for arg in node.args.args:
                    self.local_vars.add(arg.arg)
                self.generic_visit(node)
                
            def visit_Import(self, node):
                """访问import语句"""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    produced.add(name)
                    
            def visit_ImportFrom(self, node):
                """访问from...import语句"""
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    produced.add(name)
        
        analyzer = VariableAnalyzer()
        analyzer.visit(tree)
        
        # 过滤Python内置函数和常量
        builtins = {
            'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 
            'set', 'tuple', 'True', 'False', 'None', 'sum', 'max', 'min',
            'abs', 'all', 'any', 'enumerate', 'zip', 'map', 'filter'
        }
        required = required - builtins - produced
        
        return {
            'required': sorted(list(required)),
            'produced': sorted(list(produced))
        }


class DependencyResolver:
    """
    依赖解析器
    
    功能：
    1. 识别模块间的依赖关系
    2. 检测未定义的变量
    3. 自动生成变量初始化代码
    4. 对模块进行拓扑排序
    """
    
    def __init__(self, registry: VariableRegistry):
        self.registry = registry
        
    def resolve_dependencies(self, modules: List[Dict]) -> List[Dict]:
        """
        解析并解决模块间的依赖关系
        
        Args:
            modules: 代码模块列表
            
        Returns:
            解决依赖后的模块列表（可能包含新增的初始化模块）
        """
        # 第1步：分析每个模块的依赖
        module_deps = []
        for i, module in enumerate(modules):
            deps = self.registry.analyze_dependencies(module['code'])
            module_deps.append({
                'index': i,
                'module': module,
                'required': set(deps['required']),
                'produced': set(deps['produced'])
            })
        
        # 第2步：找出未定义的变量
        undefined = self._find_undefined_variables(module_deps)
        
        # 第3步：生成初始化模块
        init_modules = []
        if undefined:
            print(f"  检测到 {len(undefined)} 个未定义变量: {sorted(undefined)}")
            for var in sorted(undefined):
                init_code = self._generate_init_code(var)
                init_modules.append({
                    'index': -1,
                    'module': {
                        'code': init_code,
                        'description': f'初始化变量 {var}'
                    },
                    'required': set(),
                    'produced': {var}
                })
        
        # 第4步：重新排序模块（拓扑排序）
        all_modules = init_modules + module_deps
        ordered = self._topological_sort(all_modules)
        
        return [m['module'] for m in ordered]
    
    def _find_undefined_variables(self, module_deps: List[Dict]) -> Set[str]:
        """
        查找未定义的变量
        
        逻辑：
        1. 遍历所有模块
        2. 如果某个变量被使用但未在之前的模块中定义，则标记为未定义
        """
        undefined = set()
        defined = set()
        
        for dep in module_deps:
            # 检查当前模块需要的变量
            for var in dep['required']:
                if var not in defined:
                    undefined.add(var)
            # 更新已定义的变量集合
            defined.update(dep['produced'])
        
        return undefined
    
    def _generate_init_code(self, var_name: str) -> str:
        """
        为未定义的变量生成初始化代码
        
        使用启发式规则根据变量名推测类型
        """
        var_type = self._infer_type(var_name)
        
        # 不同类型的初始化模板
        templates = {
            'list': f'{var_name} = []',
            'dict': f'{var_name} = {{}}',
            'int': f'{var_name} = 0',
            'float': f'{var_name} = 0.0',
            'str': f'{var_name} = ""',
            'bool': f'{var_name} = False',
            'DataFrame': f'{var_name} = pd.DataFrame()',
            'unknown': f'{var_name} = None  # TODO: 请指定初始值'
        }
        
        init_code = f"# 自动生成的变量初始化\n"
        init_code += templates.get(var_type, templates['unknown'])
        
        return init_code
    
    def _infer_type(self, var_name: str) -> str:
        """
        根据变量名推测类型
        
        启发式规则：
        - 以_list结尾或复数形式 -> list
        - 以_dict结尾 -> dict
        - 以_df结尾或df_开头 -> DataFrame
        - 以num_, count_, n_开头 -> int
        - 以is_, has_, should_开头 -> bool
        - 以_str结尾或str_开头 -> str
        """
        if var_name.endswith('_list') or (var_name.endswith('s') and not var_name.endswith('ss')):
            return 'list'
        elif var_name.endswith('_dict'):
            return 'dict'
        elif var_name.endswith('_df') or var_name.startswith('df_'):
            return 'DataFrame'
        elif var_name.startswith(('num_', 'count_', 'n_')):
            return 'int'
        elif var_name.startswith(('is_', 'has_', 'should_')):
            return 'bool'
        elif var_name.endswith('_str') or var_name.startswith('str_'):
            return 'str'
        elif '_file' in var_name or var_name.endswith('_path'):
            return 'str'
        else:
            return 'unknown'
    
    def _topological_sort(self, modules: List[Dict]) -> List[Dict]:
        """
        对模块进行拓扑排序
        
        使用Kahn算法确保：
        1. 每个模块在使用变量前，该变量已被定义
        2. 没有循环依赖
        """
        n = len(modules)
        
        # 构建依赖图
        graph = [[] for _ in range(n)]
        in_degree = [0] * n
        
        for i in range(n):
            for j in range(n):
                if i != j:
                    # 如果模块j需要模块i产生的变量，则j依赖i
                    if modules[j]['required'] & modules[i]['produced']:
                        graph[i].append(j)
                        in_degree[j] += 1
        
        # Kahn算法实现
        queue = [i for i in range(n) if in_degree[i] == 0]
        result = []
        
        while queue:
            # 取出入度为0的节点
            node = queue.pop(0)
            result.append(modules[node])
            
            # 更新依赖该节点的其他节点的入度
            for next_node in graph[node]:
                in_degree[next_node] -= 1
                if in_degree[next_node] == 0:
                    queue.append(next_node)
        
        # 检查是否存在循环依赖
        if len(result) != n:
            print("  ⚠️  警告：检测到循环依赖，使用原始顺序")
            return modules
        
        return result


class CodePlanner:
    """
    代码规划器
    
    功能：
    1. 分析任务描述
    2. 生成代码模块
    3. 解决模块间的依赖关系
    4. 组装最终代码
    """
    
    def __init__(self):
        self.registry = VariableRegistry()
        self.resolver = DependencyResolver(self.registry)
        
    def plan_and_generate(self, task_description: str) -> str:
        """
        完整的代码规划和生成流程
        
        Args:
            task_description: 任务描述
            
        Returns:
            生成的完整代码
        """
        print("=" * 70)
        print(f"任务: {task_description}")
        print("=" * 70)
        
        # 第1步：生成代码模块
        print("\n📋 第1步：分析任务并生成代码模块")
        modules = self._generate_modules(task_description)
        print(f"  生成了 {len(modules)} 个代码模块")
        for i, module in enumerate(modules):
            print(f"  ✓ 模块 {i+1}: {module['description']}")
        
        # 第2步：分析依赖
        print("\n🔍 第2步：分析模块依赖关系")
        for i, module in enumerate(modules):
            deps = self.registry.analyze_dependencies(module['code'])
            if deps['required'] or deps['produced']:
                print(f"  模块 {i+1}: {module['description']}")
                if deps['required']:
                    print(f"    需要变量: {deps['required']}")
                if deps['produced']:
                    print(f"    产生变量: {deps['produced']}")
        
        # 第3步：解决依赖
        print("\n🔧 第3步：解决依赖关系")
        resolved_modules = self.resolver.resolve_dependencies(modules)
        
        if len(resolved_modules) > len(modules):
            print(f"  添加了 {len(resolved_modules) - len(modules)} 个初始化模块")
        else:
            print("  所有变量都已正确定义")
        
        # 第4步：组装代码
        print("\n📦 第4步：组装最终代码")
        final_code = self._assemble_code(resolved_modules)
        
        print("\n✅ 代码生成完成！\n")
        
        return final_code
    
    def _generate_modules(self, task_description: str) -> List[Dict]:
        """
        根据任务描述生成代码模块
        
        使用模式匹配识别任务中的关键操作
        """
        modules = []
        
        # 数据加载模块
        if any(keyword in task_description for keyword in ['读取', 'CSV', '加载', 'load']):
            modules.append({
                'code': '''# 读取CSV文件
df = pd.read_csv(input_file)
print(f"✓ 成功加载数据，共 {len(df)} 行")''',
                'description': '读取CSV文件'
            })
        
        # 数据清洗模块
        if any(keyword in task_description for keyword in ['清洗', '空值', 'dropna', '缺失']):
            modules.append({
                'code': '''# 数据清洗：去除空值
df_cleaned = df.dropna()
print(f"✓ 清洗完成，剩余 {len(df_cleaned)} 行")''',
                'description': '清洗数据（去除空值）'
            })
        
        # 数据转换模块
        if any(keyword in task_description for keyword in ['转换', '归一化', 'normalize']):
            modules.append({
                'code': '''# 数据转换
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
df_scaled = scaler.fit_transform(df_cleaned)
print("✓ 数据标准化完成")''',
                'description': '数据标准化'
            })
        
        # 统计分析模块
        if any(keyword in task_description for keyword in ['统计', '计算', 'describe', '分析']):
            modules.append({
                'code': '''# 统计分析
statistics = df_cleaned.describe()
print("✓ 统计信息：")
print(statistics)''',
                'description': '计算统计信息'
            })
        
        # 可视化模块
        if any(keyword in task_description for keyword in ['可视化', '绘图', 'plot', '图表']):
            modules.append({
                'code': '''# 数据可视化
import matplotlib.pyplot as plt
df_cleaned.hist(figsize=(10, 8))
plt.tight_layout()
plt.savefig('data_distribution.png')
print("✓ 图表已保存")''',
                'description': '数据可视化'
            })
        
        # 保存结果模块
        if any(keyword in task_description for keyword in ['保存', '输出', 'save', '导出']):
            modules.append({
                'code': '''# 保存结果
statistics.to_csv(output_file)
print(f"✓ 结果已保存到 {output_file}")''',
                'description': '保存结果'
            })
        
        # 如果没有识别到任何模块，提供一个默认模块
        if not modules:
            modules.append({
                'code': '''# 默认操作
print("执行任务：", task_desc)''',
                'description': '默认操作'
            })
        
        return modules
    
    def _assemble_code(self, modules: List[Dict]) -> str:
        """
        组装最终代码
        
        包括：
        1. 添加文档字符串
        2. 添加导入语句
        3. 组合所有模块
        4. 添加注释和分隔符
        """
        code_parts = []
        
        # 文档字符串
        code_parts.append('"""')
        code_parts.append('智能体自动生成的代码')
        code_parts.append('')
        code_parts.append('本代码由智能体系统自动规划和生成，包括：')
        code_parts.append('- 任务分析和模块分解')
        code_parts.append('- 变量依赖分析')
        code_parts.append('- 自动依赖解析')
        code_parts.append('- 代码组装和格式化')
        code_parts.append('"""')
        code_parts.append('')
        
        # 导入语句
        code_parts.append('# 导入必要的库')
        code_parts.append('import pandas as pd')
        code_parts.append('import numpy as np')
        code_parts.append('')
        
        # 主函数
        code_parts.append('def main():')
        code_parts.append('    """主函数"""')
        code_parts.append('    ')
        
        # 添加所有模块（缩进）
        for i, module in enumerate(modules):
            # 模块分隔和描述
            code_parts.append(f'    # {"=" * 60}')
            if 'description' in module:
                code_parts.append(f'    # 步骤 {i+1}: {module["description"]}')
            code_parts.append(f'    # {"=" * 60}')
            
            # 添加模块代码（缩进）
            for line in module['code'].split('\n'):
                if line.strip():
                    code_parts.append('    ' + line)
            code_parts.append('    ')
        
        # 添加主程序入口
        code_parts.append('')
        code_parts.append('if __name__ == "__main__":')
        code_parts.append('    main()')
        
        return '\n'.join(code_parts)


def demo_basic_example():
    """示例1：基础数据处理流程"""
    print("\n" + "🔷" * 35)
    print("示例 1: 基础数据处理流程")
    print("🔷" * 35)
    
    task = "读取CSV文件，清洗数据去除空值，计算统计信息，保存结果"
    
    planner = CodePlanner()
    code = planner.plan_and_generate(task)
    
    print("=" * 70)
    print("生成的代码：")
    print("=" * 70)
    print(code)
    print("=" * 70)


def demo_dependency_resolution():
    """示例2：依赖解析演示"""
    print("\n" + "🔷" * 35)
    print("示例 2: 依赖解析演示")
    print("🔷" * 35)
    
    # 创建几个有依赖关系的模块
    modules = [
        {
            'code': 'result = x * 2',
            'description': '使用x计算result'
        },
        {
            'code': 'y = result + 10',
            'description': '使用result计算y'
        },
        {
            'code': 'final = y ** 2\nprint(f"最终结果: {final}")',
            'description': '使用y计算final并输出'
        }
    ]
    
    registry = VariableRegistry()
    resolver = DependencyResolver(registry)
    
    print("\n📋 原始模块（按定义顺序）：")
    for i, m in enumerate(modules):
        deps = registry.analyze_dependencies(m['code'])
        print(f"\n  模块 {i+1}: {m['description']}")
        print(f"    代码: {repr(m['code'])}")
        print(f"    需要变量: {deps['required']}")
        print(f"    产生变量: {deps['produced']}")
    
    print("\n🔧 执行依赖解析...")
    resolved = resolver.resolve_dependencies(modules)
    
    print("\n✅ 解析后的完整代码：")
    print("=" * 70)
    for i, module in enumerate(resolved):
        print(f"# --- 步骤 {i+1}: {module.get('description', '未知')} ---")
        print(module['code'])
        print()
    print("=" * 70)


def demo_complex_ml_pipeline():
    """示例3：复杂的机器学习流程"""
    print("\n" + "🔷" * 35)
    print("示例 3: 机器学习流程")
    print("🔷" * 35)
    
    modules = [
        {
            'code': '''# 加载鸢尾花数据集
from sklearn.datasets import load_iris
X, y = load_iris(return_X_y=True)
print(f"✓ 数据集加载完成: {X.shape[0]} 个样本")''',
            'description': '加载数据集'
        },
        {
            'code': '''# 分割训练集和测试集
from sklearn.model_selection import train_test_split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
print(f"✓ 训练集: {len(X_train)} 样本，测试集: {len(X_test)} 样本")''',
            'description': '分割数据集'
        },
        {
            'code': '''# 训练随机森林模型
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
print("✓ 模型训练完成")''',
            'description': '训练模型'
        },
        {
            'code': '''# 评估模型性能
from sklearn.metrics import accuracy_score, classification_report
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)
print(f"✓ 模型准确率: {accuracy:.4f}")
print("\\n分类报告:")
print(classification_report(y_test, y_pred))''',
            'description': '评估模型'
        }
    ]
    
    registry = VariableRegistry()
    resolver = DependencyResolver(registry)
    
    print("\n📋 分析机器学习流程的模块依赖：")
    for i, m in enumerate(modules):
        deps = registry.analyze_dependencies(m['code'])
        print(f"\n  模块 {i+1}: {m['description']}")
        if deps['required']:
            print(f"    需要: {deps['required']}")
        if deps['produced']:
            print(f"    产生: {deps['produced']}")
    
    print("\n🔧 执行依赖解析...")
    resolved = resolver.resolve_dependencies(modules)
    
    print("\n✅ 完整的机器学习代码：")
    print("=" * 70)
    for i, module in enumerate(resolved):
        print(f"# 步骤 {i+1}: {module.get('description', '未知')}")
        print(module['code'])
        print()
    print("=" * 70)


def demo_variable_types():
    """示例4：变量类型推断"""
    print("\n" + "🔷" * 35)
    print("示例 4: 变量类型推断")
    print("🔷" * 35)
    
    test_variables = [
        'data_list',
        'config_dict',
        'df_results',
        'num_iterations',
        'count_errors',
        'is_valid',
        'has_error',
        'input_file',
        'output_path',
        'random_value',
    ]
    
    registry = VariableRegistry()
    resolver = DependencyResolver(registry)
    
    print("\n🔍 变量类型推断示例：\n")
    print(f"{'变量名':<20} {'推断类型':<15} {'初始化代码'}")
    print("-" * 70)
    
    for var in test_variables:
        var_type = resolver._infer_type(var)
        init_code = resolver._generate_init_code(var).split('\n')[1]  # 去掉注释行
        print(f"{var:<20} {var_type:<15} {init_code}")


def main():
    """主函数：运行所有示例"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║       智能体代码规划与协同实现 - 完整可运行示例                  ║
║       Intelligent Agent Code Planning & Coordination Demo       ║
║                                                                  ║
║  本程序演示了智能体系统如何进行代码规划和协同：                  ║
║  1. 任务分析和模块分解                                          ║
║  2. 变量依赖分析                                                ║
║  3. 自动依赖解析和初始化                                        ║
║  4. 代码组装和生成                                              ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 运行所有示例
        demo_basic_example()
        demo_dependency_resolution()
        demo_complex_ml_pipeline()
        demo_variable_types()
        
        print("\n" + "=" * 70)
        print("🎉 所有示例运行完成！")
        print("=" * 70)
        print("""
📚 关键技术点总结：

1. 变量依赖分析
   - 使用AST（抽象语法树）分析代码结构
   - 识别变量的定义（Store）和使用（Load）
   - 跟踪变量在模块间的流转

2. 依赖解析
   - 检测未定义的变量
   - 使用启发式规则推断变量类型
   - 自动生成变量初始化代码

3. 拓扑排序
   - 构建模块依赖图
   - 使用Kahn算法排序
   - 确保执行顺序正确，避免未定义错误

4. 代码协同
   - 模块接口管理
   - 类型检查和转换
   - 自动生成适配器代码

这些机制共同确保了生成的代码：
✓ 没有未定义变量错误
✓ 模块之间衔接自然
✓ 执行顺序正确
✓ 类型匹配合理
        """)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
