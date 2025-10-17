# src/Agent/GoT/graph.py

from pydantic import BaseModel, Field
from typing import Dict, List, Literal

# 定义一个概念节点可能处于的所有状态
ConceptStatus = Literal["unexplored", "exploring", "grounded", "synthesized", "failed"]

class ConceptNode(BaseModel):
    """
    定义图中的一个节点，代表一个数学概念。
    """
    name: str
    status: ConceptStatus = "unexplored"
    dependencies: List[str] = Field(default_factory=list)
    formal_code: str | None = None
    error_message: str | None = None
    informal_description: str | None = None
    
    def __repr__(self) -> str:
        """提供一个清晰的字符串表示，方便调试。"""
        return f"Node(name='{self.name}', status='{self.status}')"

class DependencyGraph(BaseModel):
    """
    管理所有 ConceptNode 的图结构，作为 GoT Agent 的“工作台”。
    """
    nodes: Dict[str, ConceptNode] = Field(default_factory=dict)

    def add_concept(self, name: str, informal_description: str | None = None) -> ConceptNode:
        """向图中添加一个新概念，如果它不存在的话。"""
        if name not in self.nodes:
            self.nodes[name] = ConceptNode(name=name, informal_description=informal_description)
        elif informal_description:
            self.nodes[name].informal_description
        return self.nodes[name]

    def add_dependency(self, parent_concept: str, child_concept: str):
        """添加一条从 parent 到 child 的依赖边。"""
        parent_node = self.add_concept(parent_concept)
        self.add_concept(child_concept)
        if child_concept not in parent_node.dependencies:
            parent_node.dependencies.append(child_concept)
            
    def get_next_unexplored_leaf(self) -> ConceptNode | None:
        """
        找到一个可以开始处理的、未探索的“叶子”节点。
        一个节点是“叶子”，意味着它的所有依赖项（如果有的话）都已经被探索过了。
        """
        for node in self.nodes.values():
            if node.status == "unexplored":
                if all(self.nodes.get(dep_name).status != "unexplored" 
                       for dep_name in node.dependencies):
                    return node
        return None
        
    def get_ready_to_synthesize_node(self) -> ConceptNode | None:
        """
        找到一个可以开始生成代码的节点（其所有依赖都已成功完成）。
        """
        for node in self.nodes.values():
            if node.status == "exploring":
                if node.dependencies and all(self.nodes[dep_name].status in ["grounded", "synthesized"] 
                       for dep_name in node.dependencies):
                    return node
        return None

    def is_complete(self, target_concept: str) -> bool:
        """检查目标概念是否已成功完成。"""
        if target_concept not in self.nodes:
            return False
        return self.nodes[target_concept].status in ["grounded", "synthesized"]