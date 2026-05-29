"""
策略文件云存储服务
自动保存大模型返回的原始文件和解析后的Python文件到腾讯云COS
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from ..models import StrategyGenerationResult

try:
    from backend.shared.cos_service import get_cos_service
except ImportError:

    def get_cos_service():
        return None


class StrategyCloudStorage:
    """策略文件云存储服务"""

    def __init__(self):
        self.cos_service = get_cos_service()

    def save_strategy_files_to_cos(
        self,
        strategy_result: StrategyGenerationResult,
        raw_response: dict[str, Any],
        strategy_id: str,
        user_id: str = None,
        user_description: str = "",
    ) -> dict[str, Any]:
        """
        保存策略相关文件到COS

        Args:
            strategy_result: 策略生成结果
            raw_response: 大模型原始响应
            strategy_id: 策略ID
            user_id: 用户ID
            user_description: 用户描述

        Returns:
            Dict: 保存结果，包含文件信息
        """
        if not self.cos_service:
            return {"success": False, "error": "COS服务不可用", "files": []}

        try:
            # 生成时间戳用于文件命名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            user_folder = user_id or "anonymous"

            saved_files = []

            # 1. 保存原始JSON响应文件
            raw_json_filename = f"output_原始数据_{strategy_id}_{timestamp}.json"
            raw_json_result = self._upload_raw_response(
                raw_response,
                raw_json_filename,
                strategy_id,
                user_folder,
                user_description,
            )
            saved_files.append(raw_json_result)

            # 2. 保存解析后的Python文件
            if strategy_result.artifacts:
                python_filename = f"output_解析结果_{strategy_id}_{timestamp}.py"
                python_result = self._upload_parsed_code(
                    strategy_result,
                    python_filename,
                    strategy_id,
                    user_folder,
                    user_description,
                )
                saved_files.append(python_result)

                # 3. 保存策略元数据文件
            metadata_filename = f"output_元数据_{strategy_id}_{timestamp}.json"
            metadata_result = self._upload_metadata(
                strategy_result,
                raw_response,
                metadata_filename,
                strategy_id,
                user_folder,
                user_description,
            )
            saved_files.append(metadata_result)

            return {
                "success": True,
                "strategy_id": strategy_id,
                "user_id": user_folder,
                "timestamp": timestamp,
                "total_files": len(saved_files),
                "files": saved_files,
                "storage_url": f"strategies/{user_folder}/{timestamp}",
            }

        except Exception as e:
            return {"success": False, "error": f"云存储保存失败: {str(e)}", "files": []}

    def _upload_raw_response(
        self,
        raw_response: dict[str, Any],
        filename: str,
        strategy_id: str,
        user_folder: str,
        user_description: str,
    ) -> dict[str, Any]:
        """上传原始响应文件"""
        try:
            # 准备文件内容
            file_content = json.dumps(raw_response, ensure_ascii=False, indent=2)

            # 添加文件头注释
            file_header = f"""# 大模型策略生成原始响应文件
# 策略ID: {strategy_id}
# 用户ID: {user_folder}
# 用户描述: {user_description}
# 生成时间: {datetime.now().isoformat()}
# 生成来源: {raw_response.get('metadata', {}).get('provider', 'unknown')}

"""

            full_content = file_header + "\n" + file_content

            # 上传到COS
            folder = f"strategies/{user_folder}/raw-responses/{datetime.now().strftime('%Y/%m')}"
            result = self.cos_service.upload_file(
                file_data=full_content,
                file_name=filename,
                folder=folder,
                content_type="application/json",
            )

            if result["success"]:
                result.update(
                    {
                        "file_type": "raw_response",
                        "description": "大模型原始响应数据",
                        "strategy_id": strategy_id,
                    }
                )

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"原始响应文件上传失败: {str(e)}",
                "file_type": "raw_response",
            }

    def _upload_parsed_code(
        self,
        strategy_result: StrategyGenerationResult,
        filename: str,
        strategy_id: str,
        user_folder: str,
        user_description: str,
    ) -> dict[str, Any]:
        """上传解析后的Python代码文件"""
        try:
            if not strategy_result.artifacts:
                return {
                    "success": False,
                    "error": "没有找到策略代码",
                    "file_type": "parsed_code",
                }

                # 获取策略代码
            strategy_code = strategy_result.artifacts[0].code

            # 准备文件内容
            file_content = f"""# AI生成策略代码 - {datetime.now().isoformat()}
# 策略ID: {strategy_id}
# 生成时间: {datetime.now().strftime('%Y/%m/%d %H:%M:%S')}

{strategy_code}

# 文件生成完成
print("策略代码已生成并保存")
"""

            # 上传到COS
            folder = f"strategies/{user_folder}/parsed-code/{datetime.now().strftime('%Y/%m')}"
            result = self.cos_service.upload_file(
                file_data=file_content,
                file_name=filename,
                folder=folder,
                content_type="text/x-python",
            )

            if result["success"]:
                result.update(
                    {
                        "file_type": "parsed_code",
                        "description": "解析后的Python策略代码",
                        "strategy_id": strategy_id,
                        "language": strategy_result.artifacts[0].language,
                    }
                )

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"解析代码文件上传失败: {str(e)}",
                "file_type": "parsed_code",
            }

    def _upload_metadata(
        self,
        strategy_result: StrategyGenerationResult,
        raw_response: dict[str, Any],
        filename: str,
        strategy_id: str,
        user_folder: str,
        user_description: str,
    ) -> dict[str, Any]:
        """上传策略元数据文件"""
        try:
            # 准备元数据
            metadata = {
                "strategy_info": {
                    "strategy_id": strategy_id,
                    "strategy_name": strategy_result.strategy_name,
                    "rationale": strategy_result.rationale,
                    "provider": strategy_result.provider,
                    "generated_at": raw_response.get("generated_at"),
                    "user_id": user_folder,
                    "user_description": user_description,
                    "timestamp": datetime.now().isoformat(),
                },
                "raw_response": {
                    "timestamp": raw_response.get("timestamp"),
                    "metadata": raw_response.get("metadata", {}),
                    "provider": raw_response.get("provider"),
                },
                "parsing_info": {
                    "success": True,
                    "artifacts_count": len(strategy_result.artifacts),
                    "factors": strategy_result.metadata.factors,
                    "risk_controls": strategy_result.metadata.risk_controls,
                    "assumptions": strategy_result.metadata.assumptions,
                    "notes": strategy_result.metadata.notes,
                },
            }

            # 添加文件头注释
            file_header = f"""# 策略生成元数据文件
# 策略ID: {strategy_id}
# 用户ID: {user_folder}
# 生成时间: {datetime.now().isoformat()}

"""

            file_content = file_header + "\n" + json.dumps(metadata, ensure_ascii=False, indent=2)

            # 上传到COS
            folder = f"strategies/{user_folder}/metadata/{datetime.now().strftime('%Y/%m')}"
            result = self.cos_service.upload_file(
                file_data=file_content,
                file_name=filename,
                folder=folder,
                content_type="application/json",
            )

            if result["success"]:
                result.update(
                    {
                        "file_type": "metadata",
                        "description": "策略生成元数据信息",
                        "strategy_id": strategy_id,
                    }
                )

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"元数据文件上传失败: {str(e)}",
                "file_type": "metadata",
            }

    def list_strategy_files(
        self,
        user_id: str | None = None,
        date_filter: str | None = None,
        file_type: str | None = None,
    ) -> dict[str, Any]:
        """
        列出策略文件

        Args:
            user_id: 用户ID过滤
            date_filter: 日期过滤 (格式: YYYY-MM)
            file_type: 文件类型过滤 (raw_responses, parsed-code, metadata)

        Returns:
            Dict: 文件列表结果
        """
        if not self.cos_service:
            return {"success": False, "error": "COS服务不可用", "files": []}

        try:
            # 构建基础路径
            base_folder = "strategies"
            if user_id:
                base_folder = f"{base_folder}/{user_id}"

                # 根据文件类型过滤
            if file_type:
                if file_type == "raw_responses":
                    folder = f"{base_folder}/raw-responses"
                elif file_type == "parsed-code":
                    folder = f"{base_folder}/parsed-code"
                elif file_type == "metadata":
                    folder = f"{base_folder}/metadata"
                else:
                    folder = base_folder
            else:
                folder = base_folder

                # 根据日期过滤
            if date_filter:
                folder = f"{folder}/{date_filter}"

                # 添加月份层级
            if not date_filter:
                current_month = datetime.now().strftime("%Y/%m")
                folder = f"{folder}/{current_month}"

            result = self.cos_service.list_files(folder=folder, max_keys=1000)

            if result["success"]:
                # 解析文件名，提取策略ID信息
                for file_info in result["files"]:
                    filename = file_info["file_key"].split("/")[-1]
                    file_info["filename"] = filename

                    # 尝试从文件名中提取策略ID
                    if "_" in filename:
                        parts = filename.split("_")
                        if len(parts) >= 3 and parts[0] in ["output"]:
                            file_info["strategy_id"] = parts[2] if len(parts) > 2 else ""

                    file_info["file_type"] = self._detect_file_type(folder, filename)

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"文件列表获取失败: {str(e)}",
                "files": [],
            }

    def _detect_file_type(self, folder: str, filename: str) -> str:
        """检测文件类型"""
        if "raw-responses" in folder:
            return "raw_response"
        elif "parsed-code" in folder:
            return "parsed_code"
        elif "metadata" in folder:
            return "metadata"
        else:
            # 根据文件名推断
            if "原始数据" in filename:
                return "raw_response"
            elif "解析结果" in filename:
                return "parsed_code"
            elif "元数据" in filename:
                return "metadata"
            else:
                return "unknown"

    def get_strategy_file_urls(self, strategy_id: str, file_types: list | None = None) -> dict[str, Any]:
        """
        获取策略相关文件的URL

        Args:
            strategy_id: 策略ID
            file_types: 要获取的文件类型列表，如果为None则获取所有类型

        Returns:
            Dict: 文件URL信息
        """
        if not self.cos_service:
            return {"success": False, "error": "COS服务不可用", "files": {}}

        try:
            # 默认获取所有类型的文件
            if not file_types:
                file_types = ["raw_response", "parsed_code", "metadata"]

            result = {"success": True, "strategy_id": strategy_id, "files": {}}

            # 遍历所有文件类型
            for file_type in file_types:
                files = []

                # 搜索策略相关的文件
                search_result = self.cos_service.list_files(folder=f"strategies/*/{strategy_id}*", max_keys=50)

                if search_result["success"]:
                    for file_info in search_result["files"]:
                        detected_type = self._detect_file_type(
                            file_info["file_key"], file_info["file_key"].split("/")[-1]
                        )
                        if detected_type == file_type or file_type == "all":
                            files.append(file_info)

                result["files"][file_type] = files

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"文件URL获取失败: {str(e)}",
                "files": {},
            }

    def is_service_available(self) -> bool:
        """检查COS服务是否可用"""
        return self.cos_service is not None and self.cos_service.is_connected()

        # 创建全局策略云存储实例


strategy_cloud_storage = StrategyCloudStorage()


def get_strategy_cloud_storage() -> StrategyCloudStorage:
    """获取策略云存储服务实例"""
    return strategy_cloud_storage
