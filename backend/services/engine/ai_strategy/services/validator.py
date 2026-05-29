"""
统一验证服务
提供参数、代码、模板的验证功能
"""

import ast
import re
import time
from typing import Any, Dict, List, Optional

from ..models import get_template_by_id
from ..models.validation import (
    CODE_QUALITY_METRICS,
    STRATEGY_PARAMETER_RULES,
    BatchValidationRequest,
    BatchValidationResponse,
    CodeValidationRequest,
    CodeValidationResponse,
    ParameterValidationError,
    ParameterValidationRequest,
    ParameterValidationResponse,
    RangeRule,
    TemplateValidationRequest,
    TemplateValidationResponse,
    ValidationError,
)

# 导入共享枚举
try:
    pass
except ImportError:
    _ValidationErrorType = str
    _ValidationSeverity = str


class ParameterValidator:
    """参数验证器"""

    def __init__(self):
        self.rules = STRATEGY_PARAMETER_RULES

    def validate_parameters(self, request: ParameterValidationRequest) -> ParameterValidationResponse:
        """验证策略参数"""
        start_time = time.time()
        errors = []
        warnings = []
        suggestions = []
        adjusted_params = request.parameters.copy()

        # 验证每个字段
        for rule in self.rules:
            field_value = request.parameters.get(rule.field)

            if not rule.validate(field_value):
                error = ParameterValidationError(
                    field=rule.field,
                    message=rule.message,
                    severity=rule.severity,
                    current_value=field_value,
                    rule=rule.rule,
                )

                if rule.severity == "error":
                    errors.append(error)
                else:
                    warnings.append(error)

                # 尝试自动调整
                suggested_value = self._suggest_value(rule.field, field_value, request.parameters)
                if suggested_value is not None:
                    adjusted_params[rule.field] = suggested_value
                    error.suggested_value = suggested_value

        # 参数一致性检查
        consistency_errors = self._check_parameter_consistency(request.parameters)
        errors.extend(consistency_errors)

        # 生成建议
        if request.include_suggestions:
            suggestions = self._generate_suggestions(request.parameters, errors, warnings)

        # 计算得分
        score = self._calculate_score(errors, warnings)

        processing_time = int((time.time() - start_time) * 1000)

        return ParameterValidationResponse(
            success=len(errors) == 0,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions,
            adjusted_parameters=(adjusted_params if adjusted_params != request.parameters else None),
            score=score,
            processing_time=processing_time,
        )

    def _suggest_value(self, field: str, value: Any, all_params: dict[str, Any]) -> Any:
        """建议值"""
        if value is None or value == "":
            # 根据其他参数推断默认值
            if field == "initial_capital":
                return 100000
            elif field == "position_size":
                risk_level = all_params.get("risk_level", "medium")
                return {"low": 5, "medium": 10, "high": 20}.get(risk_level, 10)
            elif field == "max_positions":
                risk_level = all_params.get("risk_level", "medium")
                return {"low": 3, "medium": 5, "high": 8}.get(risk_level, 5)
            elif field == "stop_loss":
                risk_level = all_params.get("risk_level", "medium")
                return {"low": 3, "medium": 5, "high": 8}.get(risk_level, 5)
            elif field == "take_profit":
                risk_level = all_params.get("risk_level", "medium")
                return {"low": 10, "medium": 20, "high": 30}.get(risk_level, 20)
            elif field == "max_drawdown":
                risk_level = all_params.get("risk_level", "medium")
                return {"low": 5, "medium": 15, "high": 25}.get(risk_level, 15)

        # 范围调整
        for rule in self.rules:
            if rule.field == field and isinstance(rule, RangeRule):
                if rule.min_val is not None:
                    try:
                        num_val = float(value)
                        if num_val < rule.min_val:
                            return rule.min_val
                        elif rule.max_val is not None and num_val > rule.max_val:
                            return rule.max_val
                    except (ValueError, TypeError):
                        pass
        return None

    def _check_parameter_consistency(self, params: dict[str, Any]) -> list[ParameterValidationError]:
        """检查参数一致性"""
        errors = []

        # 检查风险等级与其他参数的一致性
        risk_level = params.get("risk_level")
        if risk_level:
            # 检查止损止盈比例
            stop_loss = params.get("stop_loss")
            take_profit = params.get("take_profit")

            if stop_loss and take_profit:
                if float(take_profit) <= float(stop_loss):
                    errors.append(
                        ParameterValidationError(
                            field="take_profit",
                            message="止盈比例必须大于止损比例",
                            severity="error",
                            current_value=take_profit,
                            suggested_value=float(stop_loss) * 3,
                        )
                    )

            # 检查资金配置
            position_size = params.get("position_size")
            max_positions = params.get("max_positions")

            if position_size and max_positions:
                total_position = float(position_size) * int(max_positions)
                if total_position > 100:
                    errors.append(
                        ParameterValidationError(
                            field="max_positions",
                            message=f"总仓位不能超过100%，当前为{total_position}%",
                            severity="warning",
                            current_value=max_positions,
                            suggested_value=int(100 / float(position_size)),
                        )
                    )

        return errors

    def _generate_suggestions(self, params: dict[str, Any], errors: list, warnings: list) -> list[str]:
        """生成建议"""
        suggestions = []

        # 基于错误生成建议
        if any(e.field == "description" for e in errors):
            suggestions.append("建议提供详细的策略描述，有助于生成更准确的策略")

        if any(e.field == "initial_capital" for e in errors):
            suggestions.append("建议初始资金不少于10,000元，确保有足够的资金进行交易")

        # 基于参数组合生成建议
        risk_level = params.get("risk_level")
        if risk_level == "high":
            suggestions.append("高风险策略建议设置更严格的止损和仓位管理")
        elif risk_level == "low":
            suggestions.append("低风险策略可以考虑增加仓位大小以提高收益")

        # 基于缺失参数生成建议
        optional_params = ["max_drawdown", "commission_rate", "slippage", "benchmark"]
        missing_params = [p for p in optional_params if p not in params]
        if missing_params:
            suggestions.append(f"建议完善以下参数以获得更准确的回测结果：{', '.join(missing_params)}")

        return suggestions

    def _calculate_score(self, errors: list, warnings: list) -> float:
        """计算验证得分"""
        base_score = 100.0

        # 错误扣分
        error_penalty = len(errors) * 20

        # 警告扣分
        warning_penalty = len(warnings) * 5

        return max(0, base_score - error_penalty - warning_penalty)


class CodeValidator:
    """代码验证器"""

    def validate_code(self, request: CodeValidationRequest) -> CodeValidationResponse:
        """验证代码"""
        start_time = time.time()
        syntax_errors = []
        logic_errors = []
        warnings = []
        suggestions = []

        # 语法验证
        syntax_errors = self._validate_syntax(request.code)

        # 逻辑验证（仅在语法正确时进行）
        if not syntax_errors:
            logic_errors = self._validate_logic(request.code, request.parameters)
            warnings = self._analyze_code_quality(request.code)

        # 生成建议
        suggestions = self._generate_code_suggestions(request.code, syntax_errors, logic_errors, warnings)

        # 计算质量得分
        quality_score = self._calculate_quality_score(request.code, syntax_errors, logic_errors, warnings)

        # 计算复杂度
        complexity = self._calculate_complexity(request.code)

        processing_time = int((time.time() - start_time) * 1000)

        return CodeValidationResponse(
            success=len(syntax_errors) == 0,
            is_valid=len(syntax_errors) == 0 and len(logic_errors) == 0,
            syntax_errors=syntax_errors,
            logic_errors=logic_errors,
            warnings=warnings,
            suggestions=suggestions,
            quality_score=quality_score,
            complexity=complexity,
            processing_time=processing_time,
            metadata={
                "language": request.language,
                "stage": request.stage,
                "line_count": len(request.code.split("\n")),
                "char_count": len(request.code),
            },
        )

    def _validate_syntax(self, code: str) -> list[ValidationError]:
        """验证语法"""
        errors = []

        try:
            # 使用AST解析Python代码
            ast.parse(code)
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    line=e.lineno,
                    column=e.offset,
                    message=f"语法错误: {e.msg}",
                    type="syntax",
                    severity="error",
                    code="SYNTAX_ERROR",
                )
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    line=1,
                    column=1,
                    message=f"解析错误: {str(e)}",
                    type="syntax",
                    severity="error",
                    code="PARSE_ERROR",
                )
            )

        # 检查基本语法问题
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            # 检查行长度
            if len(line) > CODE_QUALITY_METRICS["max_line_length"]:
                errors.append(
                    ValidationError(
                        line=i,
                        column=CODE_QUALITY_METRICS["max_line_length"],
                        message=f"行过长 ({len(line)} 字符)",
                        type="syntax",
                        severity="warning",
                        code="LONG_LINE",
                    )
                )

            # 检查缩进
            if line.strip() and not line.startswith(" ") and not line.startswith("\t"):
                if i > 1:  # 第一行可以是顶格
                    if any(lines[j].strip() for j in range(max(0, i - 5), i - 1)):
                        errors.append(
                            ValidationError(
                                line=i,
                                column=1,
                                message="缩进不一致",
                                type="syntax",
                                severity="error",
                                code="INDENTATION_ERROR",
                            )
                        )

        return errors

    def _validate_logic(self, code: str, parameters: dict[str, Any] | None) -> list[ValidationError]:
        """验证逻辑"""
        errors = []

        try:
            tree = ast.parse(code)

            # 检查必需函数
            defined_functions = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    defined_functions.append(node.name)

            # 检查是否包含必需函数
            required_functions = CODE_QUALITY_METRICS["required_functions"]
            missing_functions = [f for f in required_functions if f not in defined_functions]

            for func in missing_functions:
                errors.append(
                    ValidationError(
                        line=1,
                        column=1,
                        message=f"缺少必需函数: {func}",
                        type="logic",
                        severity="error",
                        code="MISSING_FUNCTION",
                    )
                )

            # 检查风险控制
            if any("stop_loss" in code.lower() for line in code.split("\n")):
                pass  # 有止损控制
            else:
                errors.append(
                    ValidationError(
                        line=1,
                        column=1,
                        message="未发现止损机制，建议添加风险控制",
                        type="logic",
                        severity="warning",
                        code="MISSING_STOP_LOSS",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    line=1,
                    column=1,
                    message=f"逻辑分析失败: {str(e)}",
                    type="logic",
                    severity="error",
                    code="LOGIC_ANALYSIS_ERROR",
                )
            )

        return errors

    def _analyze_code_quality(self, code: str) -> list[ValidationError]:
        """分析代码质量"""
        warnings = []

        # 检查注释比例
        lines = code.split("\n")
        code_lines = [line for line in lines if line.strip() and not line.strip().startswith("#")]
        comment_lines = [line for line in lines if line.strip().startswith("#")]

        if code_lines:
            comment_ratio = len(comment_lines) / len(code_lines)
            if comment_ratio < CODE_QUALITY_METRICS["min_comment_ratio"]:
                warnings.append(
                    ValidationError(
                        line=1,
                        column=1,
                        message="注释过少，建议添加更多注释说明",
                        type="logic",
                        severity="warning",
                        code="LOW_COMMENT_RATIO",
                    )
                )

        # 检查函数长度
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno + 1
                    if func_lines > CODE_QUALITY_METRICS["max_function_length"]:
                        warnings.append(
                            ValidationError(
                                line=node.lineno,
                                _column=1,
                                message=f"函数过长 ({func_lines} 行)，建议拆分",
                                type="logic",
                                severity="warning",
                                code="LONG_FUNCTION",
                            )
                        )
        except Exception:
            pass

        return warnings

    def _generate_code_suggestions(
        self, code: str, syntax_errors: list, logic_errors: list, warnings: list
    ) -> list[str]:
        """生成代码建议"""
        suggestions = []

        if syntax_errors:
            suggestions.append("修复语法错误后重新验证")

        if logic_errors:
            suggestions.append("完善策略逻辑，确保包含所有必需功能")

        if not any("import" in line for line in code.split("\n")):
            suggestions.append("添加必要的导入语句，如 pandas, numpy等")

        if not any("class" in line for line in code.split("\n")):
            suggestions.append("建议使用面向对象的方式组织代码")

        if warnings:
            suggestions.append("根据警告信息优化代码质量")

        # 检查是否包含数据验证
        if not any("dropna" in line or "isnull" in line for line in code.split("\n")):
            suggestions.append("建议添加数据验证和清洗逻辑")

        return suggestions

    def _calculate_quality_score(self, code: str, syntax_errors: list, logic_errors: list, warnings: list) -> float:
        """计算代码质量得分"""
        base_score = 100.0

        # 语法错误扣分
        syntax_penalty = len(syntax_errors) * 30

        # 逻辑错误扣分
        logic_penalty = len(logic_errors) * 20

        # 警告扣分
        warning_penalty = len(warnings) * 5

        # 复杂度扣分
        complexity = self._calculate_complexity(code)
        if complexity > CODE_QUALITY_METRICS["complexity_threshold"]:
            complexity_penalty = (complexity - CODE_QUALITY_METRICS["complexity_threshold"]) * 0.5
        else:
            complexity_penalty = 0

        return max(
            0,
            base_score - syntax_penalty - logic_penalty - warning_penalty - complexity_penalty,
        )

    def _calculate_complexity(self, code: str) -> int:
        """计算代码复杂度"""
        complexity = 0

        # 基于AST节点计算复杂度
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # 不同节点类型的复杂度权重
                if isinstance(node, (ast.If, ast.For, ast.While)):
                    complexity += 1
                elif isinstance(node, ast.Try):
                    complexity += 1
                elif isinstance(node, ast.ListComp):
                    complexity += 1
                elif isinstance(node, ast.DictComp):
                    complexity += 1
                elif isinstance(node, ast.Lambda):
                    complexity += 1
        except Exception:
            # 如果解析失败，基于文本计算
            complexity = len(re.findall(r"\b(if|for|while|try|except|lambda|def|class)\b", code))

        return complexity


class TemplateValidator:
    """模板验证器"""

    def validate_template_compatibility(self, request: TemplateValidationRequest) -> TemplateValidationResponse:
        """验证模板兼容性"""
        start_time = time.time()
        errors = []
        suggestions = []
        adaptations = []

        # 获取模板
        template = get_template_by_id(request.template_id)
        if not template:
            return TemplateValidationResponse(
                success=False,
                is_valid=False,
                template_id=request.template_id,
                compatibility_score=0.0,
                errors=[
                    ParameterValidationError(
                        field="template_id",
                        message=f"模板 {request.template_id} 不存在",
                        severity="error",
                        current_value=request.template_id,
                    )
                ],
                processing_time=int((time.time() - start_time) * 1000),
            )

        # 验证参数兼容性
        param_errors = self._validate_template_parameters(template, request.parameters)
        errors.extend(param_errors)

        # 计算兼容性得分
        compatibility_score = self._calculate_compatibility_score(template, request.parameters)

        # 生成适配建议
        adaptations = self._generate_adaptations(template, request.parameters)

        # 生成建议
        suggestions = self._generate_template_suggestions(template, request.parameters, errors)

        processing_time = int((time.time() - start_time) * 1000)

        return TemplateValidationResponse(
            success=len([e for e in errors if e.severity == "error"]) == 0,
            is_valid=len([e for e in errors if e.severity == "error"]) == 0,
            template_id=request.template_id,
            compatibility_score=compatibility_score,
            errors=errors,
            _warnings=[e for e in errors if e.severity == "warning"],
            suggestions=suggestions,
            adaptations=adaptations,
            processing_time=processing_time,
        )

    def _validate_template_parameters(self, template, parameters: dict[str, Any]) -> list[ParameterValidationError]:
        """验证模板参数"""
        errors = []

        # 检查必需参数
        for rule in template.validation_rules:
            field_value = parameters.get(rule.field)

            if not self._validate_rule(rule, field_value):
                errors.append(
                    ParameterValidationError(
                        field=rule.field,
                        message=rule.message,
                        severity=rule.severity,
                        current_value=field_value,
                        rule=rule.rule,
                    )
                )

        # 检查资金要求
        initial_capital = parameters.get("initial_capital")
        if initial_capital and initial_capital < template.min_capital:
            errors.append(
                ParameterValidationError(
                    field="initial_capital",
                    message=f"初始资金低于模板最低要求 ({template.min_capital}元)",
                    severity="error",
                    current_value=initial_capital,
                    suggested_value=template.min_capital,
                )
            )

        # 检查市场兼容性
        market = parameters.get("market")
        if market and market not in template.suitable_markets:
            errors.append(
                ParameterValidationError(
                    _field="market",
                    _message=f"市场 {market} 不适合此模板",
                    _severity="warning",
                    _current_value=market,
                    _suggested_value=(template.suitable_markets[0] if template.suitable_markets else "CN"),
                )
            )

        return errors

    def _validate_rule(self, rule, value: Any) -> bool:
        """验证单个规则"""
        if rule.rule == "required":
            return value is not None and value != ""
        elif rule.rule.startswith("min:"):
            min_val = float(rule.rule.split(":")[1])
            try:
                return float(value) >= min_val
            except (ValueError, TypeError):
                return False
        elif rule.rule.startswith("max:"):
            max_val = float(rule.rule.split(":")[1])
            try:
                return float(value) <= max_val
            except (ValueError, TypeError):
                return False
        return True

    def _calculate_compatibility_score(self, template, parameters: dict[str, Any]) -> float:
        """计算兼容性得分"""
        score = 0.5  # 基础分

        # 市场匹配
        market = parameters.get("market")
        if market and market in template.suitable_markets:
            score += 0.2

        # 风险等级匹配
        risk_level = parameters.get("risk_level")
        if risk_level and risk_level in template.suitable_risk_levels:
            score += 0.15

        # 时间框架匹配
        timeframe = parameters.get("timeframe")
        if timeframe and timeframe in template.suitable_timeframes:
            score += 0.1

        # 资金适配
        initial_capital = parameters.get("initial_capital")
        if initial_capital:
            if initial_capital >= template.min_capital * 2:
                score += 0.05
            elif initial_capital >= template.min_capital:
                score += 0.02

        return min(1.0, score)

    def _generate_adaptations(self, template, parameters: dict[str, Any]) -> list[str]:
        """生成适配建议"""
        adaptations = []

        # 资金适配建议
        initial_capital = parameters.get("initial_capital")
        if initial_capital and initial_capital < template.min_capital:
            adaptations.append(f"建议增加初始资金至{template.min_capital:,}元以上")

        # 市场适配建议
        market = parameters.get("market")
        if market and market not in template.suitable_markets:
            adaptations.append(f"建议切换到适合的市场：{', '.join(template.suitable_markets)}")

        # 风险适配建议
        risk_level = parameters.get("risk_level")
        if risk_level and risk_level not in template.suitable_risk_levels:
            suitable_risks = template.suitable_risk_levels
            if suitable_risks:
                adaptations.append(f"建议调整风险等级为：{', '.join(suitable_risks)}")

        return adaptations

    def _generate_template_suggestions(self, template, parameters: dict[str, Any], errors: list) -> list[str]:
        """生成模板建议"""
        suggestions = []

        if not errors:
            suggestions.append("参数配置良好，可以使用此模板生成策略")
        else:
            suggestions.append("请根据错误信息调整参数配置")

        # 基于模板特性给出建议
        if template.metadata.complexity == "high":
            suggestions.append("这是复杂策略模板，建议仔细检查参数配置")

        if template.min_capital > 100000:
            suggestions.append(f"此模板需要较多资金（最少{template.min_capital:,}元）")

        return suggestions


class UnifiedValidator:
    """统一验证器"""

    def __init__(self):
        self.parameter_validator = ParameterValidator()
        self.code_validator = CodeValidator()
        self.template_validator = TemplateValidator()

    def validate_batch(self, request: BatchValidationRequest) -> BatchValidationResponse:
        """批量验证"""
        start_time = time.time()
        results = {}

        # 参数验证
        if request.parameters and ("parameters" in request.validation_types or "all" in request.validation_types):
            param_request = ParameterValidationRequest(parameters=request.parameters, strict_mode=request.strict_mode)
            results["parameter_validation"] = self.parameter_validator.validate_parameters(param_request)

        # 代码验证
        if request.code and ("code" in request.validation_types or "all" in request.validation_types):
            code_request = CodeValidationRequest(
                code=request.code,
                parameters=request.parameters,
                strict_mode=request.strict_mode,
            )
            results["code_validation"] = self.code_validator.validate_code(code_request)

        # 模板验证
        if request.template_id and ("template" in request.validation_types or "all" in request.validation_types):
            template_request = TemplateValidationRequest(
                _template_id=request.template_id,
                parameters=request.parameters or {},
                _strict_mode=request.strict_mode,
            )
            results["template_validation"] = self.template_validator.validate_template_compatibility(template_request)

        # 计算综合得分
        scores = []
        for key, result in results.items():
            if hasattr(result, "score"):
                scores.append(result.score)
            elif hasattr(result, "quality_score"):
                scores.append(result.quality_score)
            elif hasattr(result, "compatibility_score"):
                scores.append(result.compatibility_score * 100)

        overall_score = sum(scores) / len(scores) if scores else 0

        # 判断是否准备好生成
        is_ready = self._is_ready_for_generation(results)

        # 生成下一步建议
        next_steps = self._generate_next_steps(results)

        processing_time = int((time.time() - start_time) * 1000)

        return BatchValidationResponse(
            _success=True,
            parameter_validation=results.get("parameter_validation"),
            code_validation=results.get("code_validation"),
            template_validation=results.get("template_validation"),
            _overall_score=overall_score,
            is_ready_for_generation=is_ready,
            next_steps=next_steps,
            _processing_time=processing_time,
        )

    def _is_ready_for_generation(self, results: dict[str, Any]) -> bool:
        """判断是否准备好生成"""
        if "parameter_validation" in results:
            param_result = results["parameter_validation"]
            if not param_result.is_valid:
                return False

        if "code_validation" in results:
            code_result = results["code_validation"]
            if not code_result.is_valid:
                return False

        if "template_validation" in results:
            template_result = results["template_validation"]
            if not template_result.is_valid:
                return False
            if template_result.compatibility_score < 0.7:
                return False

        return True

    def _generate_next_steps(self, results: dict[str, Any]) -> list[str]:
        """生成下一步建议"""
        steps = []

        if "parameter_validation" in results:
            param_result = results["parameter_validation"]
            if param_result.errors:
                steps.append("修正参数验证错误")
            if param_result.adjusted_parameters:
                steps.append("查看参数调整建议")

        if "code_validation" in results:
            code_result = results["code_validation"]
            if code_result.syntax_errors:
                steps.append("修复代码语法错误")
            if code_result.logic_errors:
                steps.append("完善代码逻辑")

        if "template_validation" in results:
            template_result = results["template_validation"]
            if template_result.errors:
                steps.append("解决模板兼容性问题")
            if template_result.adaptations:
                steps.append("考虑模板适配建议")

        if not steps:
            steps.append("参数和代码验证通过，可以开始生成策略")

        return steps


# 全局验证器实例
unified_validator = UnifiedValidator()
