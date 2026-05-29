"""
文件安全验证模块
提供文件类型检查、内容安全扫描、恶意文件检测等功能
"""

import io
import os
import re
import zipfile
from typing import Any, Dict, List

import magic
from loguru import logger
from PIL import Image

try:
    import pyclamd

    CLAMD_AVAILABLE = True
except ImportError:
    CLAMD_AVAILABLE = False
    logger.warning("pyclamd未安装，病毒扫描功能将不可用")

try:
    pass

    YARA_AVAILABLE = True
except ImportError:
    YARA_AVAILABLE = False
    logger.warning("yara-python未安装，高级恶意文件检测功能将不可用")


class FileSecurityValidator:
    """文件安全验证器"""

    def __init__(self):
        """初始化文件安全验证器"""
        self.magic = magic.Magic(mime=True)
        self.dangerous_extensions = {
            # 可执行文件
            ".exe",
            ".bat",
            ".cmd",
            ".com",
            ".pi",
            ".scr",
            ".vbs",
            ".js",
            ".jar",
            ".ps1",
            ".sh",
            ".php",
            ".asp",
            ".aspx",
            ".jsp",
            ".py",
            ".rb",
            ".pl",
            # 脚本和宏
            ".msh",
            ".msi",
            ".msp",
            ".mst",
            ".reg",
            ".ws",
            ".wsc",
            # 其他危险文件
            ".app",
            ".deb",
            ".rpm",
            ".dmg",
            ".pkg",
            ".iso",
            ".img",
            ".bin",
        }

        self.dangerous_signatures = [
            # PE文件签名
            b"MZ\x90\x00",  # DOS header
            b"\x7fEL",  # ELF header
            b"\xca\xfe\xba\xbe",  # Java class file
            b"\xfe\xed\xfa",  # Mach-O binary (macOS)
            b"PK\x03\x04",  # ZIP archive (可能包含恶意内容)
            b"\x1f\x8b",  # GZIP archive
        ]

        self.script_patterns = [
            r"<script[^>]*>.*?</script>",  # HTML/JS scripts
            r"eval\s*\(",  # JavaScript eval
            r"document\.write\s*\(",  # DOM manipulation
            r"<iframe[^>]*>",  # iframes
            r"javascript:",  # JavaScript URLs
            r"vbscript:",  # VBScript
        ]

        self.max_filename_length = 255
        self.max_path_length = 1024

    def validate_filename(self, filename: str) -> dict[str, Any]:
        """
        验证文件名安全性

        Args:
            filename: 文件名

        Returns:
            Dict: 验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "sanitized_filename": filename,
        }

        # 检查文件名长度
        if len(filename) > self.max_filename_length:
            result["valid"] = False
            result["errors"].append(f"文件名过长，最大长度: {self.max_filename_length}")

        # 检查危险字符
        dangerous_chars = ["..", "/", "\\", ":", "*", "?", '"', "<", ">", "|", "\0"]
        for char in dangerous_chars:
            if char in filename:
                result["valid"] = False
                result["errors"].append(f"文件名包含危险字符: {repr(char)}")

        # 检查文件扩展名
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext in self.dangerous_extensions:
            result["valid"] = False
            result["errors"].append(f"不允许的文件类型: {file_ext}")

        # 检查可疑文件名模式
        suspicious_patterns = [
            r".*\.(exe|bat|cmd|scr)\.(zip|rar|7z)$",  # 伪装的可执行文件
            r"^\.",  # 隐藏文件
            r".*[<>|&;].*",  # 包含shell特殊字符
        ]

        for pattern in suspicious_patterns:
            if re.match(pattern, filename, re.IGNORECASE):
                result["warnings"].append(f"可疑的文件名模式: {pattern}")

        # 清理文件名
        sanitized = filename
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "_")

        # 限制清理后的文件名长度
        name, ext = os.path.splitext(sanitized)
        if len(name) > 100:
            name = name[:100]
        result["sanitized_filename"] = f"{name}{ext}"

        return result

    def validate_file_type(self, file_data: bytes, filename: str) -> dict[str, Any]:
        """
        验证文件类型真实性

        Args:
            file_data: 文件数据
            filename: 文件名

        Returns:
            Dict: 验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "detected_type": None,
            "expected_type": None,
        }

        try:
            # 使用python-magic检测文件类型
            detected_mime = self.magic.from_buffer(file_data)
            result["detected_type"] = detected_mime

            # 根据文件扩展名确定期望的类型
            file_ext = os.path.splitext(filename)[1].lower()
            expected_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gi": "image/gi",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".pd": "application/pd",
                ".txt": "text/plain",
                ".csv": "text/csv",
                ".json": "application/json",
            }

            result["expected_type"] = expected_types.get(file_ext)

            # 检查文件类型是否匹配
            if result["expected_type"] and detected_mime:
                if not detected_mime.startswith(result["expected_type"].split("/")[0]):
                    result["warnings"].append(f"文件类型不匹配: 期望 {result['expected_type']}, 检测到 {detected_mime}")

            # 检查文件头签名
            self._check_file_signatures(file_data, result)

        except Exception as e:
            result["warnings"].append(f"文件类型检测失败: {str(e)}")

        return result

    def _check_file_signatures(self, file_data: bytes, result: dict[str, Any]):
        """检查文件头签名"""
        # 检查危险文件签名
        for signature in self.dangerous_signatures:
            if file_data.startswith(signature):
                result["valid"] = False
                result["errors"].append(f"检测到危险文件签名: {signature.hex()}")

        # 特定文件类型的深度检查
        if len(file_data) > 4:
            # ZIP文件检查
            if file_data.startswith(b"PK\x03\x04"):
                self._check_zip_file(file_data, result)

            # 图片文件深度检查
            if result["detected_type"] and result["detected_type"].startswith("image/"):
                self._check_image_file(file_data, result)

    def _check_zip_file(self, file_data: bytes, result: dict[str, Any]):
        """检查ZIP文件安全性"""
        try:
            # 在内存中打开ZIP文件
            zip_file = io.BytesIO(file_data)
            with zipfile.ZipFile(zip_file, "r") as zip_ref:
                # 检查ZIP炸弹
                total_size = sum(info.file_size for info in zip_ref.filelist)
                if total_size > 100 * 1024 * 1024:  # 100MB
                    result["valid"] = False
                    result["errors"].append("ZIP文件解压后大小过大，可能为ZIP炸弹")

                # 检查文件数量
                if len(zip_ref.filelist) > 1000:
                    result["warnings"].append("ZIP文件包含过多文件")

                # 检查可疑文件名
                for info in zip_ref.filelist:
                    filename_validation = self.validate_filename(info.filename)
                    if not filename_validation["valid"]:
                        result["valid"] = False
                        result["errors"].extend(filename_validation["errors"])

                    # 检查压缩比例
                    if info.compress_size > 0 and info.file_size / info.compress_size > 100:
                        result["warnings"].append(f"文件 {info.filename} 压缩比异常")

        except Exception as e:
            result["warnings"].append(f"ZIP文件检查失败: {str(e)}")

    def _check_image_file(self, file_data: bytes, result: dict[str, Any]):
        """检查图片文件安全性"""
        try:
            # 使用PIL检查图片
            img = Image.open(io.BytesIO(file_data))

            # 检查图片尺寸
            if img.width > 10000 or img.height > 10000:
                result["warnings"].append("图片尺寸过大")

            # 检查图片文件大小合理性
            expected_size = img.width * img.height * 3  # RGB格式
            if len(file_data) > expected_size * 10:  # 允许10倍的压缩误差
                result["warnings"].append("图片文件大小异常，可能包含隐藏数据")

            # 检查EXIF数据（可能包含恶意脚本）
            if hasattr(img, "_getexi") and img._getexif():
                img._getexif()
                # 这里可以添加更详细的EXIF检查

        except Exception as e:
            result["warnings"].append(f"图片文件检查失败: {str(e)}")

    def scan_for_malware(self, file_data: bytes, filename: str) -> dict[str, Any]:
        """
        扫描恶意软件

        Args:
            file_data: 文件数据
            filename: 文件名

        Returns:
            Dict: 扫描结果
        """
        result = {
            "scanned": False,
            "malware_detected": False,
            "threats": [],
            "engine": "none",
            "errors": [],
        }

        # ClamAV扫描
        if CLAMD_AVAILABLE:
            try:
                cd = pyclamd.ClamdUnixSocket()
                scan_result = cd.scan_stream(file_data)

                if scan_result:
                    result["scanned"] = True
                    result["engine"] = "clamav"

                    if scan_result.get("stream"):
                        threat_info = scan_result["stream"]
                        if "FOUND" in threat_info:
                            result["malware_detected"] = True
                            result["threats"].append(threat_info)

            except Exception as e:
                result["errors"].append(f"ClamAV扫描失败: {str(e)}")

        # YARA规则扫描
        if YARA_AVAILABLE and not result["malware_detected"]:
            try:
                # 这里应该加载YARA规则文件
                # rules = yara.compile(source='rule Malware { strings: $malware = "malware_pattern" condition: $malware }')
                # matches = rules.match(data=file_data)
                #
                # if matches:
                #     result['scanned'] = True
                #     result['engine'] = 'yara'
                #     result['malware_detected'] = True
                #     result['threats'].extend([match.rule for match in matches])
                pass  # YARA规则需要单独配置
            except Exception as e:
                result["errors"].append(f"YARA扫描失败: {str(e)}")

        # 基础特征检测
        if not result["malware_detected"]:
            self._basic_malware_detection(file_data, result)

        return result

    def _basic_malware_detection(self, file_data: bytes, result: dict[str, Any]):
        """基础恶意文件检测"""
        # 检查脚本注入
        content = file_data.decode("utf-8", errors="ignore").lower()

        for pattern in self.script_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                result["threats"].append(f"检测到可疑脚本模式: {pattern}")

        # 检查常见恶意字符串
        malicious_strings = [
            "eval(base64_decode",
            "shell_exec",
            "system(",
            "passthru(",
            "exec(",
            "document.cookie",
            "window.location",
            "<script",
            "javascript:",
        ]

        found_strings = [s for s in malicious_strings if s in content]
        if found_strings:
            result["threats"].extend(found_strings)

        if result["threats"]:
            result["scanned"] = True
            result["engine"] = "basic"

    def validate_file_content(self, file_data: bytes, category: str = "general") -> dict[str, Any]:
        """
        验证文件内容安全性

        Args:
            file_data: 文件数据
            category: 文件类别

        Returns:
            Dict: 验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "security_level": "safe",  # safe, suspicious, dangerous
            "metadata": {},
        }

        try:
            # 根据类别进行不同的验证
            if category in ["avatar", "image"]:
                self._validate_image_content(file_data, result)
            elif category == "document":
                self._validate_document_content(file_data, result)
            elif category == "archive":
                self._validate_archive_content(file_data, result)

            # 通用验证
            self._validate_generic_content(file_data, result)

        except Exception as e:
            result["errors"].append(f"内容验证失败: {str(e)}")
            result["valid"] = False

        # 确定安全级别
        if result["errors"]:
            result["security_level"] = "dangerous"
            result["valid"] = False
        elif result["warnings"]:
            result["security_level"] = "suspicious"

        return result

    def _validate_image_content(self, file_data: bytes, result: dict[str, Any]):
        """验证图片内容"""
        try:
            img = Image.open(io.BytesIO(file_data))

            # 提取元数据
            result["metadata"].update(
                {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                    "has_transparency": img.mode in ("RGBA", "LA") or "transparency" in img.info,
                }
            )

            # 检查图片合理性
            if img.width < 1 or img.height < 1:
                result["errors"].append("图片尺寸无效")
                return

            if img.width > 20000 or img.height > 20000:
                result["warnings"].append("图片尺寸过大")

            # 检查像素数据
            pixels = list(img.getdata())
            if len(pixels) != img.width * img.height:
                result["warnings"].append("图片像素数据异常")

        except Exception as e:
            result["errors"].append(f"图片格式验证失败: {str(e)}")

    def _validate_document_content(self, file_data: bytes, result: dict[str, Any]):
        """验证文档内容"""
        # 检查文档是否包含恶意脚本
        content = file_data.decode("utf-8", errors="ignore")

        dangerous_keywords = [
            "javascript:",
            "<script",
            "eval(",
            "exec(",
            "system(",
        ]

        found_keywords = [kw for kw in dangerous_keywords if kw.lower() in content.lower()]
        if found_keywords:
            result["warnings"].append(f"文档包含可疑内容: {', '.join(found_keywords)}")

    def _validate_archive_content(self, file_data: bytes, result: dict[str, Any]):
        """验证压缩包内容"""
        if file_data.startswith(b"PK\x03\x04"):
            try:
                zip_file = io.BytesIO(file_data)
                with zipfile.ZipFile(zip_file, "r") as zip_ref:
                    result["metadata"]["file_count"] = len(zip_ref.filelist)
                    result["metadata"]["total_size"] = sum(info.file_size for info in zip_ref.filelist)

                    # 检查压缩比
                    total_compressed = sum(info.compress_size for info in zip_ref.filelist)
                    total_uncompressed = sum(info.file_size for info in zip_ref.filelist)

                    if total_uncompressed > 0:
                        ratio = total_compressed / total_uncompressed
                        if ratio < 0.01:  # 压缩比过高
                            result["warnings"].append("压缩包压缩比异常，可能包含恶意内容")

            except Exception as e:
                result["errors"].append(f"压缩包验证失败: {str(e)}")

    def _validate_generic_content(self, file_data: bytes, result: dict[str, Any]):
        """通用内容验证"""
        # 检查文件大小合理性
        if len(file_data) == 0:
            result["errors"].append("文件为空")
        elif len(file_data) > 100 * 1024 * 1024:  # 100MB
            result["warnings"].append("文件较大")

        # 检查二进制特征
        null_bytes = file_data.count(b"\x00")
        if null_bytes > len(file_data) * 0.5:
            result["warnings"].append("文件包含大量空字节")

        # 检查熵值（用于检测加密或压缩内容）
        if len(file_data) > 100:
            entropy = self._calculate_entropy(file_data[:1000])  # 取前1000字节计算
            result["metadata"]["entropy"] = entropy

            if entropy > 7.5:
                result["warnings"].append("文件熵值较高，可能为加密或压缩内容")

    def _calculate_entropy(self, data: bytes) -> float:
        """计算数据熵值"""
        if not data:
            return 0

        # 统计字节频率
        byte_counts = [0] * 256
        for byte in data:
            byte_counts[byte] += 1

        # 计算熵
        entropy = 0
        data_len = len(data)
        for count in byte_counts:
            if count > 0:
                frequency = count / data_len
                entropy -= frequency * (frequency.bit_length() - 1)

        return entropy

    def comprehensive_validation(self, file_data: bytes, filename: str, category: str = "general") -> dict[str, Any]:
        """
        综合文件安全验证

        Args:
            file_data: 文件数据
            filename: 文件名
            category: 文件类别

        Returns:
            Dict: 综合验证结果
        """
        result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "security_level": "safe",
            "filename_validation": {},
            "type_validation": {},
            "content_validation": {},
            "malware_scan": {},
            "recommendations": [],
        }

        # 1. 文件名验证
        result["filename_validation"] = self.validate_filename(filename)
        result["errors"].extend(result["filename_validation"]["errors"])
        result["warnings"].extend(result["filename_validation"]["warnings"])

        # 2. 文件类型验证
        result["type_validation"] = self.validate_file_type(file_data, filename)
        result["warnings"].extend(result["type_validation"]["warnings"])

        # 3. 内容验证
        result["content_validation"] = self.validate_file_content(file_data, category)
        result["errors"].extend(result["content_validation"]["errors"])
        result["warnings"].extend(result["content_validation"]["warnings"])

        # 4. 恶意软件扫描
        result["malware_scan"] = self.scan_for_malware(file_data, filename)
        if result["malware_scan"]["malware_detected"]:
            result["valid"] = False
            result["errors"].extend([f"检测到恶意软件: {threat}" for threat in result["malware_scan"]["threats"]])

        # 5. 生成建议
        result["recommendations"] = self._generate_recommendations(result)

        # 6. 确定最终状态
        if result["errors"]:
            result["valid"] = False
            result["security_level"] = "dangerous"
        elif len(result["warnings"]) > 3:
            result["security_level"] = "suspicious"
        elif result["warnings"]:
            result["security_level"] = "caution"

        return result

    def _generate_recommendations(self, validation_result: dict[str, Any]) -> list[str]:
        """生成安全建议"""
        recommendations = []

        if validation_result["filename_validation"]["warnings"]:
            recommendations.append("建议重命名文件，移除特殊字符")

        if validation_result["type_validation"]["warnings"]:
            recommendations.append("请确认文件类型与内容匹配")

        if validation_result["content_validation"]["warnings"]:
            recommendations.append("文件内容存在异常，建议重新上传")

        if validation_result["malware_scan"]["errors"]:
            recommendations.append("安全扫描出现问题，建议使用杀毒软件检查文件")

        if not recommendations and validation_result["warnings"]:
            recommendations.append("文件基本安全，但建议定期检查")

        return recommendations


# 创建全局文件安全验证器实例
file_security_validator = FileSecurityValidator()


def get_file_security_validator() -> FileSecurityValidator:
    """获取文件安全验证器实例"""
    return file_security_validator


def validate_file_security(file_data: bytes, filename: str, category: str = "general") -> dict[str, Any]:
    """便捷函数：验证文件安全性"""
    validator = get_file_security_validator()
    return validator.comprehensive_validation(file_data, filename, category)
