"""
DSL解析器 - 解析量化策略DSL语法
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List

from ..observability.logging import get_logger

logger = get_logger(__name__)


class TokenType(Enum):
    """DSL词法单元类型"""

    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    KEYWORD = "KEYWORD"
    OPERATOR = "OPERATOR"
    COMPARATOR = "COMPARATOR"
    LOGICAL = "LOGICAL"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    COLON = "COLON"
    NEWLINE = "NEWLINE"
    EOF = "EO"


@dataclass
class Token:
    """词法单元"""

    type: TokenType
    value: str
    line: int = 1
    column: int = 1


@dataclass
class ASTNode:
    """抽象语法树节点"""

    type: str
    value: Any = None
    children: list["ASTNode"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DSLLexer:
    """DSL词法分析器"""

    KEYWORDS = {
        "strategy",
        "define",
        "i",
        "then",
        "else",
        "for",
        "in",
        "while",
        "buy",
        "sell",
        "hold",
        "position",
        "portfolio",
        "risk",
        "indicator",
        "ma",
        "ema",
        "rsi",
        "macd",
        "bollinger",
        "volume",
        "price",
        "close",
        "open",
        "high",
        "low",
        "and",
        "or",
        "not",
        "true",
        "false",
    }

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

    def tokenize(self) -> list[Token]:
        """词法分析"""
        while self.pos < len(self.text):
            char = self.text[self.pos]

            if char.isspace():
                if char == "\n":
                    self.tokens.append(Token(TokenType.NEWLINE, char, self.line, self.column))
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.pos += 1
            elif char.isalpha() or char == "_":
                self._read_identifier()
            elif char.isdigit() or char == ".":
                self._read_number()
            elif char == '"' or char == "'":
                self._read_string()
            else:
                self._read_operator()

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.column))
        return self.tokens

    def _read_identifier(self):
        """读取标识符"""
        start_pos = self.pos
        start_col = self.column

        while self.pos < len(self.text) and (self.text[self.pos].isalnum() or self.text[self.pos] == "_"):
            self.pos += 1
            self.column += 1

        value = self.text[start_pos : self.pos]
        token_type = TokenType.KEYWORD if value in self.KEYWORDS else TokenType.IDENTIFIER
        self.tokens.append(Token(token_type, value, self.line, start_col))

    def _read_number(self):
        """读取数字"""
        start_pos = self.pos
        start_col = self.column

        while self.pos < len(self.text) and (self.text[self.pos].isdigit() or self.text[self.pos] == "."):
            self.pos += 1
            self.column += 1

        value = self.text[start_pos : self.pos]
        self.tokens.append(Token(TokenType.NUMBER, value, self.line, start_col))

    def _read_string(self):
        """读取字符串"""
        quote = self.text[self.pos]
        start_pos = self.pos + 1
        start_col = self.column

        self.pos += 1
        self.column += 1

        while self.pos < len(self.text) and self.text[self.pos] != quote:
            if self.text[self.pos] == "\\":
                self.pos += 2
                self.column += 2
            else:
                self.pos += 1
                self.column += 1

        if self.pos < len(self.text):
            value = self.text[start_pos : self.pos]
            self.pos += 1
            self.column += 1
            self.tokens.append(Token(TokenType.STRING, value, self.line, start_col))

    def _read_operator(self):
        """读取操作符"""
        char = self.text[self.pos]
        start_col = self.column

        # 多字符操作符
        if self.pos + 1 < len(self.text):
            two_char = char + self.text[self.pos + 1]
            if two_char in [">=", "<=", "==", "!=", "&&", "||"]:
                self.tokens.append(Token(TokenType.COMPARATOR, two_char, self.line, start_col))
                self.pos += 2
                self.column += 2
                return

        # 单字符操作符
        operator_map = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            ">": TokenType.COMPARATOR,
            "<": TokenType.COMPARATOR,
            "=": TokenType.OPERATOR,
            "!": TokenType.LOGICAL,
            "&": TokenType.LOGICAL,
            "|": TokenType.LOGICAL,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
            ":": TokenType.COLON,
        }

        token_type = operator_map.get(char, TokenType.OPERATOR)
        self.tokens.append(Token(token_type, char, self.line, start_col))
        self.pos += 1
        self.column += 1


class DSLParser:
    """DSL语法分析器"""

    def __init__(self):
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self.tokens = []
        self.pos = 0

    def parse(self, dsl_text: str) -> "StrategyDSL":
        """解析DSL文本"""
        try:
            # 词法分析
            lexer = DSLLexer(dsl_text)
            self.tokens = lexer.tokenize()
            self.pos = 0

            # 语法分析
            ast = self._parse_strategy()

            # 构建StrategyDSL对象
            strategy_dsl = self._build_strategy_dsl(ast)

            self.logger.info(
                "DSL parsing completed successfully",
                strategy_name=strategy_dsl.name,
                rules_count=len(strategy_dsl.rules),
            )

            return strategy_dsl

        except Exception as e:
            self.logger.error(f"DSL parsing failed: {e}")
            raise

    def _current_token(self) -> Token:
        """获取当前token"""
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token(TokenType.EOF, "")

    def _advance(self) -> Token:
        """前进到下一个token"""
        token = self._current_token()
        self.pos += 1
        return token

    def _expect(self, token_type: TokenType) -> Token:
        """期望特定类型的token"""
        token = self._current_token()
        if token.type != token_type:
            raise SyntaxError(f"Expected {token_type}, got {token.type} at line {token.line}")
        return self._advance()

    def _parse_strategy(self) -> ASTNode:
        """解析策略定义"""
        self._expect(TokenType.KEYWORD)  # strategy
        name_token = self._expect(TokenType.IDENTIFIER)

        strategy_node = ASTNode("strategy", name_token.value)

        # 解析策略体
        if self._current_token().type == TokenType.LBRACE:
            self._advance()

            while self._current_token().type != TokenType.RBRACE:
                if self._current_token().type == TokenType.EOF:
                    raise SyntaxError("Unexpected end of input")

                child = self._parse_statement()
                strategy_node.children.append(child)

            self._advance()  # }

        return strategy_node

    def _parse_statement(self) -> ASTNode:
        """解析语句"""
        token = self._current_token()

        if token.type == TokenType.KEYWORD:
            if token.value == "define":
                return self._parse_define()
            elif token.value in ["buy", "sell", "hold"]:
                return self._parse_action()
            elif token.value == "i":
                return self._parse_conditional()
            elif token.value == "for":
                return self._parse_loop()

        return self._parse_expression()

    def _parse_define(self) -> ASTNode:
        """解析定义语句"""
        self._advance()  # define
        name_token = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.OPERATOR)  # =

        expression = self._parse_expression()

        define_node = ASTNode("define", name_token.value)
        define_node.children.append(expression)

        return define_node

    def _parse_action(self) -> ASTNode:
        """解析动作语句"""
        action_token = self._advance()  # buy/sell/hold

        action_node = ASTNode("action", action_token.value)

        # 解析动作参数
        if self._current_token().type == TokenType.LPAREN:
            self._advance()

            while self._current_token().type != TokenType.RPAREN:
                param = self._parse_expression()
                action_node.children.append(param)

                if self._current_token().type == TokenType.COMMA:
                    self._advance()

            self._advance()  # )

        return action_node

    def _parse_conditional(self) -> ASTNode:
        """解析条件语句"""
        self._advance()  # if

        condition = self._parse_expression()
        self._expect(TokenType.KEYWORD)  # then
        then_branch = self._parse_statement()

        else_branch = None
        if self._current_token().type == TokenType.KEYWORD and self._current_token().value == "else":
            self._advance()
            else_branch = self._parse_statement()

        conditional_node = ASTNode("conditional")
        conditional_node.children = [condition, then_branch]
        if else_branch:
            conditional_node.children.append(else_branch)

        return conditional_node

    def _parse_loop(self) -> ASTNode:
        """解析循环语句"""
        self._advance()  # for

        # 解析循环变量和范围
        var_token = self._expect(TokenType.IDENTIFIER)
        self._expect(TokenType.KEYWORD)  # in
        range_expr = self._parse_expression()
        self._expect(TokenType.KEYWORD)  # while
        condition = self._parse_expression()

        body = self._parse_statement()

        loop_node = ASTNode("loop")
        loop_node.children = [
            ASTNode("variable", var_token.value),
            range_expr,
            condition,
            body,
        ]

        return loop_node

    def _parse_expression(self) -> ASTNode:
        """解析表达式"""
        return self._parse_logical_or()

    def _parse_logical_or(self) -> ASTNode:
        """解析逻辑或表达式"""
        left = self._parse_logical_and()

        while self._current_token().type == TokenType.LOGICAL and self._current_token().value == "or":
            op = self._advance()
            right = self._parse_logical_and()

            or_node = ASTNode("binary_op", op.value)
            or_node.children = [left, right]
            left = or_node

        return left

    def _parse_logical_and(self) -> ASTNode:
        """解析逻辑与表达式"""
        left = self._parse_comparison()

        while self._current_token().type == TokenType.LOGICAL and self._current_token().value == "and":
            op = self._advance()
            right = self._parse_comparison()

            and_node = ASTNode("binary_op", op.value)
            and_node.children = [left, right]
            left = and_node

        return left

    def _parse_comparison(self) -> ASTNode:
        """解析比较表达式"""
        left = self._parse_additive()

        while self._current_token().type == TokenType.COMPARATOR:
            op = self._advance()
            right = self._parse_additive()

            comp_node = ASTNode("binary_op", op.value)
            comp_node.children = [left, right]
            left = comp_node

        return left

    def _parse_additive(self) -> ASTNode:
        """解析加减表达式"""
        left = self._parse_multiplicative()

        while self._current_token().type == TokenType.OPERATOR and self._current_token().value in ["+", "-"]:
            op = self._advance()
            right = self._parse_multiplicative()

            add_node = ASTNode("binary_op", op.value)
            add_node.children = [left, right]
            left = add_node

        return left

    def _parse_multiplicative(self) -> ASTNode:
        """解析乘除表达式"""
        left = self._parse_primary()

        while self._current_token().type == TokenType.OPERATOR and self._current_token().value in ["*", "/"]:
            op = self._advance()
            right = self._parse_primary()

            mul_node = ASTNode("binary_op", op.value)
            mul_node.children = [left, right]
            left = mul_node

        return left

    def _parse_primary(self) -> ASTNode:
        """解析基本表达式"""
        token = self._current_token()

        if token.type == TokenType.NUMBER:
            self._advance()
            return ASTNode("number", float(token.value))
        elif token.type == TokenType.STRING:
            self._advance()
            return ASTNode("string", token.value)
        elif token.type == TokenType.IDENTIFIER:
            self._advance()

            # 函数调用
            if self._current_token().type == TokenType.LPAREN:
                return self._parse_function_call(token.value)
            else:
                return ASTNode("identifier", token.value)
        elif token.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN)
            return expr
        else:
            raise SyntaxError(f"Unexpected token: {token.type} at line {token.line}")

    def _parse_function_call(self, func_name: str) -> ASTNode:
        """解析函数调用"""
        self._advance()  # (

        func_node = ASTNode("function_call", func_name)

        while self._current_token().type != TokenType.RPAREN:
            arg = self._parse_expression()
            func_node.children.append(arg)

            if self._current_token().type == TokenType.COMMA:
                self._advance()

        self._advance()  # )
        return func_node

    def _build_strategy_dsl(self, ast: ASTNode) -> "StrategyDSL":
        """从AST构建StrategyDSL对象"""
        strategy_dsl = StrategyDSL(name=ast.value)

        for child in ast.children:
            if child.type == "define":
                var_name = child.value
                var_value = self._evaluate_expression(child.children[0])
                strategy_dsl.variables[var_name] = var_value
            elif child.type == "action":
                rule = self._build_rule_from_action(child)
                strategy_dsl.rules.append(rule)
            elif child.type == "conditional":
                rule = self._build_rule_from_conditional(child)
                strategy_dsl.rules.append(rule)

        return strategy_dsl

    def _evaluate_expression(self, expr: ASTNode) -> Any:
        """计算表达式值"""
        if expr.type == "number":
            return expr.value
        elif expr.type == "string":
            return expr.value
        elif expr.type == "identifier":
            return expr.value
        elif expr.type == "binary_op":
            left = self._evaluate_expression(expr.children[0])
            right = self._evaluate_expression(expr.children[1])

            if expr.value == "+":
                return left + right
            elif expr.value == "-":
                return left - right
            elif expr.value == "*":
                return left * right
            elif expr.value == "/":
                return left / right
            elif expr.value == ">":
                return left > right
            elif expr.value == "<":
                return left < right
            elif expr.value == ">=":
                return left >= right
            elif expr.value == "<=":
                return left <= right
            elif expr.value == "==":
                return left == right
            elif expr.value == "!=":
                return left != right
            elif expr.value == "and":
                return left and right
            elif expr.value == "or":
                return left or right

        return None

    def _build_rule_from_action(self, action_node: ASTNode) -> dict[str, Any]:
        """从动作节点构建规则"""
        rule = {
            "type": "action",
            "action": action_node.value,
            "conditions": [],
            "parameters": {},
        }

        for param in action_node.children:
            param_value = self._evaluate_expression(param)
            if isinstance(param_value, dict):
                rule["parameters"].update(param_value)
            else:
                rule["parameters"][f"param_{len(rule['parameters'])}"] = param_value

        return rule

    def _build_rule_from_conditional(self, cond_node: ASTNode) -> dict[str, Any]:
        """从条件节点构建规则"""
        condition = self._evaluate_expression(cond_node.children[0])
        then_action = (
            self._build_rule_from_action(cond_node.children[1])
            if cond_node.children[1].type == "action"
            else cond_node.children[1]
        )

        rule = {
            "type": "conditional",
            "condition": condition,
            "then_action": then_action,
            "else_action": None,
        }

        if len(cond_node.children) > 2:
            else_action = (
                self._build_rule_from_action(cond_node.children[2])
                if cond_node.children[2].type == "action"
                else cond_node.children[2]
            )
            rule["else_action"] = else_action

        return rule


@dataclass
class StrategyDSL:
    """策略DSL对象"""

    name: str
    variables: dict[str, Any] = field(default_factory=dict)
    rules: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "variables": self.variables,
            "rules": self.rules,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
