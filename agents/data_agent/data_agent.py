"""
Data Agent - 数据分析和清洗 Agent
用于数据质量检查、清洗、标准化

功能：
1. 数据质量评估
2. 重复数据检测和删除
3. 数据标准化（邮箱、URL、格式）
4. 数据补全
5. 导出管理
"""

import os
import sys
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent


@dataclass
class DataIssue:
    """数据问题"""
    issue_type: str  # invalid_email, duplicate, missing_field, invalid_url
    record_id: int
    field: str
    value: str
    severity: str  # high, medium, low


@dataclass
class DataQualityReport:
    """数据质量报告"""
    total_records: int
    valid_records: int
    issues: List[DataIssue]
    duplicates_found: int
    quality_score: float  # 0-100


class DataAgent(BaseAgent):
    """
    数据清洗和质量控制 Agent
    """

    # 验证规则
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    URL_PATTERN = re.compile(r'^https?://[^\s]+$')

    def __init__(self, name: str = "DataAgent", browser_manager=None, db=None):
        super().__init__(name, browser_manager, db)

    async def run(self, task: dict) -> Dict:
        """
        执行数据清洗任务

        Args:
            task: {
                "action": str,           # validate | deduplicate | standardize | export | full_clean
                "records": List[Dict],   # 要处理的数据
                "rules": Dict,          # 自定义规则
                "auto_fix": bool        # 是否自动修复
            }

        Returns:
            Dict: 处理结果
        """
        action = task.get("action", "full_clean")
        records = task.get("records", [])
        auto_fix = task.get("auto_fix", True)

        print(f"[DataAgent] Running data action: {action}")

        if action == "validate":
            return await self._validate_records(records)
        elif action == "deduplicate":
            return await self._deduplicate_records(records, auto_fix)
        elif action == "standardize":
            return await self._standardize_records(records, auto_fix)
        elif action == "export":
            return await self._export_records(records, task.get("format", "json"))
        else:
            return await self._full_clean(records, auto_fix)

    async def _validate_records(self, records: List[Dict]) -> Dict:
        """验证数据记录"""
        issues = []
        valid_count = 0

        seen_emails = set()
        seen_urls = set()

        for i, record in enumerate(records):
            record_issues = []
            is_valid = True

            # 验证邮箱
            email = record.get("email")
            if email:
                if not self.EMAIL_PATTERN.match(email):
                    record_issues.append(DataIssue(
                        issue_type="invalid_email",
                        record_id=i,
                        field="email",
                        value=email,
                        severity="high"
                    ))
                    is_valid = False
                elif email in seen_emails:
                    record_issues.append(DataIssue(
                        issue_type="duplicate",
                        record_id=i,
                        field="email",
                        value=email,
                        severity="medium"
                    ))
                else:
                    seen_emails.add(email)

            # 验证 URL
            url = record.get("profile_url")
            if url and not self.URL_PATTERN.match(url):
                record_issues.append(DataIssue(
                    issue_type="invalid_url",
                    record_id=i,
                    field="profile_url",
                    value=url,
                    severity="medium"
                ))
                is_valid = False

            # 检查必填字段
            required = ["platform", "username"]
            for field in required:
                if not record.get(field):
                    record_issues.append(DataIssue(
                        issue_type="missing_field",
                        record_id=i,
                        field=field,
                        value="",
                        severity="high"
                    ))
                    is_valid = False

            if record_issues:
                issues.extend(record_issues)
            else:
                valid_count += 1

        quality_score = (valid_count / len(records) * 100) if records else 0

        return {
            "total_records": len(records),
            "valid_records": valid_count,
            "issues_count": len(issues),
            "quality_score": round(quality_score, 2),
            "issues": [
                {
                    "type": i.issue_type,
                    "record_id": i.record_id,
                    "field": i.field,
                    "value": i.value,
                    "severity": i.severity
                }
                for i in issues
            ]
        }

    async def _deduplicate_records(self, records: List[Dict], auto_fix: bool) -> Dict:
        """去重"""
        seen = {}
        duplicates = []
        unique_records = []

        for record in records:
            # 使用 platform + username 作为唯一键
            key = f"{record.get('platform', '')}:{record.get('username', '')}"

            if key in seen:
                duplicates.append({
                    "original_id": seen[key],
                    "duplicate": record,
                    "key": key
                })
            else:
                seen[key] = len(unique_records)
                unique_records.append(record)

        if auto_fix:
            # 自动修复：删除重复，保留第一个
            pass
        else:
            # 只报告，不修复
            unique_records = records

        return {
            "total_records": len(records),
            "unique_records": len(unique_records),
            "duplicates_found": len(duplicates),
            "duplicates": duplicates,
            "fixed": auto_fix
        }

    async def _standardize_records(self, records: List[Dict], auto_fix: bool) -> Dict:
        """标准化数据格式"""
        standardized = []
        changes = []

        for record in records:
            new_record = record.copy()

            # 标准化邮箱（小写，去空格）
            if new_record.get("email"):
                new_email = new_record["email"].lower().strip()
                if new_email != new_record["email"]:
                    changes.append({
                        "record": record,
                        "field": "email",
                        "old": new_record["email"],
                        "new": new_email
                    })
                    new_record["email"] = new_email

            # 标准化 URL
            if new_record.get("profile_url"):
                url = new_record["profile_url"].strip()
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                if url != new_record["profile_url"]:
                    changes.append({
                        "record": record,
                        "field": "profile_url",
                        "old": new_record["profile_url"],
                        "new": url
                    })
                    new_record["profile_url"] = url

            # 标准化用户名（去除多余空格）
            if new_record.get("username"):
                new_username = " ".join(new_record["username"].split())
                if new_username != new_record["username"]:
                    changes.append({
                        "record": record,
                        "field": "username",
                        "old": new_record["username"],
                        "new": new_username
                    })
                    new_record["username"] = new_username

            standardized.append(new_record)

        return {
            "total_records": len(records),
            "standardized": len(standardized),
            "changes_made": len(changes),
            "changes": changes[:50],  # 限制返回数量
            "fixed": auto_fix
        }

    async def _export_records(self, records: List[Dict], format: str) -> Dict:
        """导出数据"""
        if format == "json":
            export_data = json.dumps(records, ensure_ascii=False, indent=2)
        elif format == "csv":
            export_data = self._to_csv(records)
        else:
            export_data = str(records)

        return {
            "format": format,
            "record_count": len(records),
            "export_data": export_data[:10000] if len(export_data) > 10000 else export_data
        }

    def _to_csv(self, records: List[Dict]) -> str:
        """转换为 CSV"""
        if not records:
            return ""

        import csv
        import io

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

        return output.getvalue()

    async def _full_clean(self, records: List[Dict], auto_fix: bool) -> Dict:
        """完整清洗流程"""
        # Step 1: 验证
        validation = await self._validate_records(records)

        # Step 2: 去重
        dedup = await self._deduplicate_records(records, auto_fix)

        # Step 3: 标准化
        standard = await self._standardize_records(records, auto_fix)

        return {
            "validation": validation,
            "deduplication": dedup,
            "standardization": standard,
            "total_cleaned": dedup.get("unique_records", len(records)),
            "issues_resolved": validation.get("issues_count", 0)
        }


# Standalone execution
async def execute_data_task(task: dict) -> Dict:
    """Execute data processing task"""
    agent = DataAgent()
    return await agent.run(task)


import json
data_agent = DataAgent
