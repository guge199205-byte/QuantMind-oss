"""云端存储 - COS 同步与管理"""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

# 导入COS服务
try:
    from backend.shared.cos_service import get_cos_service
except ImportError:

    def get_cos_service():
        return None


def save_strategy_to_cos(
    strategy_code: str, strategy_name: str, strategy_id: str, user_id: str | None
) -> dict[str, Any]:
    """
    将策略代码保存到COS

    Args:
        strategy_code: 策略代码内容
        strategy_name: 策略名称
        strategy_id: 策略ID
        user_id: 用户ID

    Returns:
        Dict: 保存结果，包含file_key和file_url
    """
    try:
        cos_service = get_cos_service()
        if not cos_service:
            logger.warning("COS服务不可用，跳过COS保存")
            return {"success": False, "error": "COS服务不可用"}

        # 创建文件内容
        file_content = f'''"""
{strategy_name}
策略ID: {strategy_id}
用户ID: {user_id}
创建时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

"""

{strategy_code}
'''

        # 生成文件名
        file_name = f"strategy_{strategy_id}.py"

        # 上传到COS
        upload_result = cos_service.upload_file(
            file_data=file_content,
            file_name=file_name,
            folder=f"strategies/{user_id or 'anonymous'}/{datetime.now().strftime('%Y/%m')}",
            content_type="text/x-python",
        )

        if upload_result["success"]:
            return {
                "success": True,
                "file_key": upload_result["file_key"],
                "file_url": upload_result["file_url"],
                "file_name": upload_result["file_name"],
            }
        else:
            return upload_result

    except Exception as e:
        logger.error("保存策略到COS失败: %s", str(e))
        return {"success": False, "error": str(e)}
