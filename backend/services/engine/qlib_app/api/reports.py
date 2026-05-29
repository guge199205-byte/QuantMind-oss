"""回测报告导出 API 路由"""

from __future__ import annotations

import io
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from backend.services.engine.qlib_app.utils.structured_logger import StructuredTaskLogger

router = APIRouter(prefix="/qlib/reports", tags=["reports"])

logger = logging.getLogger(__name__)
task_logger = StructuredTaskLogger(logger, "ReportsAPI")


def get_qlib_service() -> Any:
    """依赖注入：获取Qlib服务实例"""
    from qlib_app.main import qlib_service

    return qlib_service


@router.get("/{backtest_id}/pdf")
async def export_pdf_report(backtest_id: str, service: Any = Depends(get_qlib_service)):
    """
    导出 PDF 回测报告

    Args:
        backtest_id: 回测ID

    Returns:
        PDF 文件流
    """
    try:
        try:
            from qlib_app.services.report_generator import PDFReportGenerator
        except ModuleNotFoundError as e:
            # 在离线/最小依赖环境下允许服务启动；导出能力按需启用。
            raise HTTPException(
                status_code=503,
                detail=f"PDF 报告导出依赖缺失: {e.name}. 请安装 reportlab/Pillow 等依赖后重试。",
            )

        # 获取回测结果
        result = await service.get_result(backtest_id)
        if not result:
            raise HTTPException(status_code=404, detail="回测结果不存在")

        # 转换为字典
        result_dict = result.dict() if hasattr(result, "dict") else result

        # 生成 PDF
        generator = PDFReportGenerator()
        pdf_bytes = generator.generate(result_dict)

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=backtest_{backtest_id}.pdf"},
        )
    except HTTPException:
        raise
    except Exception as e:
        task_logger.exception("export_pdf_failed", "导出 PDF 报告失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"导出 PDF 报告失败: {str(e)}")


@router.get("/{backtest_id}/excel")
async def export_excel_report(backtest_id: str, service: Any = Depends(get_qlib_service)):
    """
    导出 Excel 回测报告

    Args:
        backtest_id: 回测ID

    Returns:
        Excel 文件流
    """
    try:
        try:
            from qlib_app.services.report_generator import ExcelReportGenerator
        except ModuleNotFoundError as e:
            raise HTTPException(
                status_code=503,
                detail=f"Excel 报告导出依赖缺失: {e.name}. 请安装 openpyxl 等依赖后重试。",
            )

        # 获取回测结果
        result = await service.get_result(backtest_id)
        if not result:
            raise HTTPException(status_code=404, detail="回测结果不存在")

        # 转换为字典
        result_dict = result.dict() if hasattr(result, "dict") else result

        # 生成 Excel
        generator = ExcelReportGenerator()
        excel_bytes = generator.generate(result_dict)

        # 返回文件流
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=backtest_{backtest_id}.xlsx"},
        )
    except HTTPException:
        raise
    except Exception as e:
        task_logger.exception("export_excel_failed", "导出 Excel 报告失败", error=str(e))
        raise HTTPException(status_code=500, detail=f"导出 Excel 报告失败: {str(e)}")
