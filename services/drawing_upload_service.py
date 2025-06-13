#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
项目图纸上传和处理服务
支持PDF图纸上传到MinIO、文本提取、向量化存储
"""

import base64
import os
import tempfile
import re
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import pymysql
import requests
from openai import OpenAI

# MinIO SDK
from minio import Minio
from minio.error import S3Error

from core.config import Config
from services.bigmodel_knowledge_base import BigModelKnowledgeBase

logger = logging.getLogger(__name__)

class DrawingUploadService:
    """项目图纸上传和处理服务"""
    
    def __init__(self):
        self.config = Config()
        
        # Gemini API配置 (使用OpenRouter)
        self.openrouter_api_key = "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"
        self.base_url = "https://openrouter.ai/api/v1"
        self.model_name = "google/gemini-2.5-pro-preview"
        
        # MinIO配置
        self.minio_endpoint = "43.139.19.144:9000"
        self.minio_access_key = "minioadmin"
        self.minio_secret_key = "minioadmin"
        self.minio_bucket_name = "drawings"
        self.minio_secure = False
        
        # MySQL配置 (使用现有的配置)
        self.mysql_config = {
            "host": "gz-cdb-e0aa423v.sql.tencentcdb.com",
            "port": 20236,
            "user": "root",
            "password": "Aa@114514",
            "database": "gauz_ai_messages"
        }
        
        # 初始化客户端
        self._init_clients()
        
        # 创建项目图纸向量知识库
        self.drawings_kb = BigModelKnowledgeBase(
            api_key=self.config.bigmodel_api_key,
            collection_name="drawings"
        )
        
        logger.info("✅ 项目图纸上传服务初始化完成")
    
    def _init_clients(self):
        """初始化各种客户端"""
        # 初始化Gemini客户端
        self.gemini_client = OpenAI(
            base_url=self.base_url,
            api_key=self.openrouter_api_key
        )
        
        # 初始化MinIO客户端
        self.minio_client = Minio(
            self.minio_endpoint,
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            secure=self.minio_secure
        )
        
        # 确保MinIO bucket存在
        try:
            if not self.minio_client.bucket_exists(self.minio_bucket_name):
                self.minio_client.make_bucket(self.minio_bucket_name)
                logger.info(f"✅ 创建MinIO bucket: {self.minio_bucket_name}")
        except Exception as e:
            logger.error(f"❌ MinIO初始化失败: {e}")
    
    def _get_mysql_connection(self):
        """获取MySQL数据库连接"""
        return pymysql.connect(
            host=self.mysql_config["host"],
            port=self.mysql_config["port"],
            user=self.mysql_config["user"],
            password=self.mysql_config["password"],
            database=self.mysql_config["database"],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
    
    def _init_drawings_table(self):
        """初始化项目图纸表"""
        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                # 创建项目图纸表
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS project_drawings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    drawing_name VARCHAR(255) NOT NULL COMMENT '图纸名称',
                    original_filename VARCHAR(255) NOT NULL COMMENT '原始文件名',
                    file_size BIGINT NOT NULL COMMENT '文件大小(字节)',
                    minio_url VARCHAR(512) NOT NULL COMMENT 'MinIO存储URL',
                    minio_object_name VARCHAR(255) NOT NULL COMMENT 'MinIO对象名',
                    extracted_text_path VARCHAR(512) COMMENT '提取的文本文件路径',
                    project_name VARCHAR(255) COMMENT '项目名称',
                    drawing_type VARCHAR(100) COMMENT '图纸类型(建筑/结构/设备等)',
                    drawing_phase VARCHAR(100) COMMENT '设计阶段(方案/初设/施工图等)',
                    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
                    process_status ENUM('uploaded', 'processing', 'completed', 'failed') DEFAULT 'uploaded' COMMENT '处理状态',
                    vector_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending' COMMENT '向量化状态',
                    vector_chunks_count INT DEFAULT 0 COMMENT '向量化文档块数量',
                    error_message TEXT COMMENT '错误信息',
                    created_by VARCHAR(100) COMMENT '上传者',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_drawing_name (drawing_name),
                    INDEX idx_project_name (project_name),
                    INDEX idx_drawing_type (drawing_type),
                    INDEX idx_upload_time (upload_time),
                    INDEX idx_process_status (process_status),
                    INDEX idx_vector_status (vector_status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目图纸信息表';
                """
                
                cursor.execute(create_table_sql)
                connection.commit()
                logger.info("✅ 项目图纸表初始化完成")
                
        except Exception as e:
            logger.error(f"❌ 初始化项目图纸表失败: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    def sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        name, ext = os.path.splitext(filename)
        name = re.sub(r'\s+', '_', name)
        name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', name)
        name = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        
        if not name:
            name = f"drawing_{int(datetime.now().timestamp())}"
        
        if len(name) > 200:
            name = name[:200].rstrip('_')
        
        return name + ext
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """生成唯一文件名"""
        name, ext = os.path.splitext(original_filename)
        unique_id = str(uuid.uuid4())[:8]
        return f"{name}_{unique_id}{ext}"
    
    def upload_to_minio(self, file_path: str, object_name: str) -> str:
        """上传文件到MinIO"""
        try:
            self.minio_client.fput_object(
                self.minio_bucket_name, 
                object_name, 
                file_path
            )
            
            scheme = "http" if not self.minio_secure else "https"
            file_url = f"{scheme}://{self.minio_endpoint}/{self.minio_bucket_name}/{object_name}"
            logger.info(f"✅ 文件已上传至MinIO: {file_url}")
            return file_url
            
        except S3Error as e:
            logger.error(f"❌ MinIO上传失败: {e}")
            raise Exception(f"MinIO上传失败: {e}")
    
    def extract_text_with_gemini(self, file_bytes: bytes, filename: str) -> str:
        """使用Gemini提取PDF图纸中的文本信息"""
        try:
            # 编码为base64
            file_base64 = base64.b64encode(file_bytes).decode('utf-8')
            data_url = f"data:application/pdf;base64,{file_base64}"
            
            prompt = """
            ## 综合信息提取指令 (Comprehensive Information Extraction Prompt)

            ### 角色与目标 (Role and Goal)
            你是一名专业的文档分析师，专攻技术和工程文档。你的核心任务是对提供的PDF文件进行一次全面、细致的信息提取，并将所有信息以结构清晰、易于阅读的格式呈现出来。最终目标是生成一份可以完全替代原始PDF进行信息查阅的详尽文字档案。

            ### 详细执行步骤 (Detailed Execution Steps)
            请严格按照以下步骤执行：

            #### 1. 完整的文本提取 (Complete Text Extraction)
            首先，提取文件中的每一段文字。这包括但不限于：
            - 主标题和各级标题
            - 所有的段落、注释、技术说明和规范描述
            - 图框（标题栏）内的所有文字：项目名称、图纸名称、图号、版本、比例、日期等
            - 所有印章、签名栏内的文字：审图机构、注册工程师信息、证书编号、有效期、审查结论等
            - 页眉、页脚以及任何页边空白处的附注文字

            #### 2. 结构化信息分类 (Structured Information Categorization)
            将提取的文本信息，使用Markdown标题进行逻辑分类。分类应至少包含（但不限于）以下几个方面：
            - ## 一、项目与单位信息 (建设单位、设计单位、审图机构等)
            - ## 二、图纸基本信息 (图纸名称、图号、版本、日期、比例等)
            - ## 三、技术参数与设计说明 (将所有设计规范、技术要点、材料要求等归入此类)
            - ## 四、审批与资质信息 (整理所有印章、签名和资质证书相关的内容)

            #### 3. 表格提取与转录 (Table Extraction and Transcription)
            识别文档中的所有表格。完整并准确地提取其内容，保持原有的行、列结构，并使用Markdown表格格式进行呈现。

            #### 4. 视觉元素描述 (Crucial: Visual Element Description)
            这是最关键的一步。对于文档中包含的任何图纸、图表、平面图或示意图，你需要提供一份详细的文字描述。你的描述应该像是在向一个无法看见图像的人解释这张图。描述应包含以下内容：
            - **主体内容**: 这张图的核心是什么？
            - **关键组成部分**: 图中显示了哪些主要元素？
            - **布局与排列**: 各个元素是如何分布的？
            - **注释与尺寸**: 图中包含了哪些重要的标签、符号和尺寸标注？
            - **图例说明**: 如果图中有图例，需要根据图例解释图中各个符号的具体含义

            ### 输出格式要求 (Output Format Requirement)
            最终交付的内容必须是单一、完整的Markdown文档。请大量使用标题、列表和表格，确保信息结构化、层次分明，易于查阅。
            """
            
            completion = self.gemini_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "file",
                                "file": {
                                    "filename": filename,
                                    "file_data": data_url
                                }
                            }
                        ]
                    }
                ],
                temperature=0.3
            )
            
            extracted_text = completion.choices[0].message.content.strip()
            logger.info(f"✅ 成功提取图纸文本，长度: {len(extracted_text)} 字符")
            return extracted_text
            
        except Exception as e:
            logger.error(f"❌ Gemini文本提取失败: {e}")
            raise Exception(f"文本提取失败: {e}")
    
    def save_extracted_text(self, text: str, filename: str) -> str:
        """保存提取的文本到临时文件"""
        try:
            # 创建文本文件目录
            txt_dir = "extracted_drawing_texts"
            os.makedirs(txt_dir, exist_ok=True)
            
            # 生成文本文件路径
            base_name = os.path.splitext(filename)[0]
            txt_filename = f"{base_name}_extracted.txt"
            txt_path = os.path.join(txt_dir, txt_filename)
            
            # 保存文本
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)
            
            logger.info(f"✅ 提取的文本已保存到: {txt_path}")
            return txt_path
            
        except Exception as e:
            logger.error(f"❌ 保存文本失败: {e}")
            raise Exception(f"保存文本失败: {e}")
    
    def vectorize_drawing_text(self, text: str, drawing_info: Dict[str, Any]) -> int:
        """将图纸文本向量化并存储到知识库"""
        try:
            # 分割文本为合适的块
            chunks = self.drawings_kb.split_document(text, chunk_size=800, chunk_overlap=100)
            
            # 准备元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                metadata = {
                    "source_file": drawing_info["drawing_name"],
                    "original_filename": drawing_info["original_filename"],
                    "project_name": drawing_info.get("project_name", "未指定"),
                    "drawing_type": drawing_info.get("drawing_type", "未指定"),
                    "drawing_phase": drawing_info.get("drawing_phase", "未指定"),
                    "chunk_index": i,
                    "chunk_count": len(chunks),
                    "document_type": "project_drawing",
                    "upload_time": datetime.now().isoformat(),
                    "drawing_id": drawing_info.get("drawing_id"),
                    "minio_url": drawing_info.get("minio_url")
                }
                metadatas.append(metadata)
            
            # 批量添加到向量知识库
            doc_ids = self.drawings_kb.add_documents_batch(chunks, metadatas)
            
            logger.info(f"✅ 图纸文本向量化完成，添加了 {len(doc_ids)} 个文档块")
            return len(doc_ids)
            
        except Exception as e:
            logger.error(f"❌ 图纸文本向量化失败: {e}")
            raise Exception(f"向量化失败: {e}")
    
    def save_drawing_info_to_mysql(self, drawing_info: Dict[str, Any]) -> int:
        """保存图纸信息到MySQL数据库"""
        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                insert_sql = """
                INSERT INTO project_drawings (
                    drawing_name, original_filename, file_size, minio_url, minio_object_name,
                    extracted_text_path, project_name, drawing_type, drawing_phase,
                    process_status, vector_status, created_by
                ) VALUES (
                    %(drawing_name)s, %(original_filename)s, %(file_size)s, %(minio_url)s, 
                    %(minio_object_name)s, %(extracted_text_path)s, %(project_name)s, 
                    %(drawing_type)s, %(drawing_phase)s, %(process_status)s, 
                    %(vector_status)s, %(created_by)s
                )
                """
                
                cursor.execute(insert_sql, drawing_info)
                connection.commit()
                
                drawing_id = cursor.lastrowid
                logger.info(f"✅ 图纸信息已保存到MySQL，ID: {drawing_id}")
                return drawing_id
                
        except Exception as e:
            logger.error(f"❌ 保存图纸信息到MySQL失败: {e}")
            if connection:
                connection.rollback()
            raise Exception(f"数据库保存失败: {e}")
        finally:
            if connection:
                connection.close()
    
    def update_drawing_status(self, drawing_id: int, 
                            process_status: str = None, 
                            vector_status: str = None,
                            vector_chunks_count: int = None,
                            error_message: str = None):
        """更新图纸处理状态"""
        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                update_fields = []
                update_values = {}
                
                if process_status:
                    update_fields.append("process_status = %(process_status)s")
                    update_values["process_status"] = process_status
                
                if vector_status:
                    update_fields.append("vector_status = %(vector_status)s")
                    update_values["vector_status"] = vector_status
                
                if vector_chunks_count is not None:
                    update_fields.append("vector_chunks_count = %(vector_chunks_count)s")
                    update_values["vector_chunks_count"] = vector_chunks_count
                
                if error_message:
                    update_fields.append("error_message = %(error_message)s")
                    update_values["error_message"] = error_message
                
                if update_fields:
                    update_fields.append("updated_at = NOW()")
                    update_values["drawing_id"] = drawing_id
                    
                    update_sql = f"""
                    UPDATE project_drawings 
                    SET {', '.join(update_fields)}
                    WHERE id = %(drawing_id)s
                    """
                    
                    cursor.execute(update_sql, update_values)
                    connection.commit()
                    logger.info(f"✅ 更新图纸状态成功，ID: {drawing_id}")
                
        except Exception as e:
            logger.error(f"❌ 更新图纸状态失败: {e}")
            if connection:
                connection.rollback()
        finally:
            if connection:
                connection.close()
    
    def check_duplicate_file(self, file_bytes: bytes, original_filename: str) -> Dict[str, Any]:
        """
        检查重复文件
        通过文件大小和原始文件名进行初步检测
        如果文件处理失败，允许重新上传
        """
        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                # 检查相同文件名和文件大小的记录
                check_sql = """
                SELECT id, drawing_name, original_filename, minio_url, upload_time, 
                       process_status, vector_status, error_message
                FROM project_drawings 
                WHERE original_filename = %s AND file_size = %s
                ORDER BY upload_time DESC
                LIMIT 1
                """
                
                cursor.execute(check_sql, (original_filename, len(file_bytes)))
                result = cursor.fetchone()
                
                if result:
                    # 如果文件处理失败，允许重新上传
                    if result["process_status"] == "failed" or result["vector_status"] == "failed":
                        logger.info(f"🔄 发现失败的文件记录，允许重新上传: {original_filename}")
                        return {
                            "is_duplicate": False,
                            "has_failed_record": True,
                            "failed_record_id": result["id"],
                            "existing_file": {
                                "id": result["id"],
                                "drawing_name": result["drawing_name"],
                                "original_filename": result["original_filename"],
                                "minio_url": result["minio_url"],
                                "upload_time": result["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
                                "process_status": result["process_status"],
                                "vector_status": result["vector_status"],
                                "error_message": result.get("error_message", "")
                            }
                        }
                    else:
                        # 文件处理成功，视为重复
                        return {
                            "is_duplicate": True,
                            "existing_file": {
                                "id": result["id"],
                                "drawing_name": result["drawing_name"],
                                "original_filename": result["original_filename"],
                                "minio_url": result["minio_url"],
                                "upload_time": result["upload_time"].strftime("%Y-%m-%d %H:%M:%S"),
                                "process_status": result["process_status"],
                                "vector_status": result["vector_status"]
                            }
                        }
                else:
                    return {"is_duplicate": False}
                    
        except Exception as e:
            logger.error(f"❌ 检查重复文件失败: {e}")
            return {"is_duplicate": False}
        finally:
            if connection:
                connection.close()

    def process_drawing_upload(self, file_bytes: bytes, 
                             original_filename: str,
                             project_name: str = None,
                             drawing_type: str = None,
                             drawing_phase: str = None,
                             created_by: str = None,
                             force_upload: bool = False) -> Dict[str, Any]:
        """
        完整处理图纸上传流程
        1. 检查重复文件
        2. 保存到临时文件
        3. 上传到MinIO
        4. 保存信息到MySQL
        5. 使用Gemini提取文本
        6. 向量化并存储到知识库
        """
        temp_file_path = None
        drawing_id = None
        
        try:
            # 1. 检查重复文件（除非强制上传）
            failed_record_id = None
            if not force_upload:
                duplicate_check = self.check_duplicate_file(file_bytes, original_filename)
                if duplicate_check["is_duplicate"]:
                    logger.info(f"⚠️ 发现重复文件: {original_filename}")
                    return {
                        "success": False,
                        "is_duplicate": True,
                        "existing_file": duplicate_check["existing_file"],
                        "message": "检测到重复文件，如需重新上传请确认"
                    }
                elif duplicate_check.get("has_failed_record"):
                    # 记录失败记录的ID，稍后删除
                    failed_record_id = duplicate_check["failed_record_id"]
                    logger.info(f"🔄 准备重新处理失败的文件: {original_filename} (旧记录ID: {failed_record_id})")
            
            # 2. 清理文件名并生成唯一名称
            clean_filename = self.sanitize_filename(original_filename)
            unique_filename = self.generate_unique_filename(clean_filename)
            
            # 3. 保存到临时文件
            temp_dir = "temp_drawings"
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, unique_filename)
            
            with open(temp_file_path, "wb") as f:
                f.write(file_bytes)
            
            # 4. 上传到MinIO
            minio_object_name = unique_filename
            minio_url = self.upload_to_minio(temp_file_path, minio_object_name)
            
            # 5. 保存基本信息到MySQL
            drawing_info = {
                "drawing_name": os.path.splitext(clean_filename)[0],
                "original_filename": original_filename,
                "file_size": len(file_bytes),
                "minio_url": minio_url,
                "minio_object_name": minio_object_name,
                "extracted_text_path": None,
                "project_name": project_name,
                "drawing_type": drawing_type,
                "drawing_phase": drawing_phase,
                "process_status": "processing",
                "vector_status": "pending",
                "created_by": created_by
            }
            
            drawing_id = self.save_drawing_info_to_mysql(drawing_info)
            drawing_info["drawing_id"] = drawing_id
            
            # 6. 使用Gemini提取文本
            logger.info(f"🔍 开始提取图纸文本: {original_filename}")
            extracted_text = self.extract_text_with_gemini(file_bytes, original_filename)
            
            # 7. 保存提取的文本
            txt_path = self.save_extracted_text(extracted_text, unique_filename)
            
            # 8. 更新文本路径
            connection = self._get_mysql_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE project_drawings SET extracted_text_path = %s WHERE id = %s",
                        (txt_path, drawing_id)
                    )
                    connection.commit()
            finally:
                connection.close()
            
            # 9. 向量化文本
            logger.info(f"🔄 开始向量化图纸文本: {original_filename}")
            self.update_drawing_status(drawing_id, vector_status="processing")
            
            vector_chunks_count = self.vectorize_drawing_text(extracted_text, drawing_info)
            
            # 10. 更新最终状态
            self.update_drawing_status(
                drawing_id, 
                process_status="completed",
                vector_status="completed",
                vector_chunks_count=vector_chunks_count
            )
            
            # 11. 删除旧的失败记录（如果存在）
            if failed_record_id and failed_record_id != drawing_id:
                try:
                    connection = self._get_mysql_connection()
                    with connection.cursor() as cursor:
                        # 删除旧的失败记录
                        cursor.execute("DELETE FROM project_drawings WHERE id = %s", (failed_record_id,))
                        connection.commit()
                        logger.info(f"🗑️ 已删除旧的失败记录: ID {failed_record_id}")
                    connection.close()
                except Exception as e:
                    logger.warning(f"⚠️ 删除旧记录失败: {e}")
            
            # 12. 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            
            result = {
                "success": True,
                "drawing_id": drawing_id,
                "drawing_name": drawing_info["drawing_name"],
                "original_filename": original_filename,
                "minio_url": minio_url,
                "extracted_text_path": txt_path,
                "vector_chunks_count": vector_chunks_count,
                "process_status": "completed",
                "vector_status": "completed"
            }
            
            logger.info(f"✅ 图纸处理完成: {original_filename}")
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 图纸处理失败: {error_msg}")
            
            # 更新错误状态
            if drawing_id:
                self.update_drawing_status(
                    drawing_id,
                    process_status="failed",
                    vector_status="failed", 
                    error_message=error_msg
                )
            
            # 清理临时文件
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass
            
            return {
                "success": False,
                "error": error_msg,
                "drawing_id": drawing_id
            }
    
    def get_drawings_list(self, project_name: str = None, 
                         drawing_type: str = None,
                         limit: int = 50) -> List[Dict[str, Any]]:
        """获取图纸列表"""
        connection = None
        try:
            connection = self._get_mysql_connection()
            with connection.cursor() as cursor:
                where_conditions = []
                params = {}
                
                if project_name:
                    where_conditions.append("project_name = %(project_name)s")
                    params["project_name"] = project_name
                
                if drawing_type:
                    where_conditions.append("drawing_type = %(drawing_type)s")
                    params["drawing_type"] = drawing_type
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                params["limit"] = limit
                
                sql = f"""
                SELECT id, drawing_name, original_filename, file_size, minio_url,
                       project_name, drawing_type, drawing_phase, process_status,
                       vector_status, vector_chunks_count, upload_time, created_by
                FROM project_drawings 
                {where_clause}
                ORDER BY upload_time DESC 
                LIMIT %(limit)s
                """
                
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                return results
                
        except Exception as e:
            logger.error(f"❌ 获取图纸列表失败: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def search_drawings_in_vector_db(self, query: str, top_k: int = 5,
                                   project_name: str = None,
                                   drawing_type: str = None) -> List[Dict[str, Any]]:
        """在向量数据库中搜索图纸相关内容"""
        try:
            # 构建过滤条件
            where_filter = {}
            if project_name:
                where_filter["project_name"] = project_name
            if drawing_type:
                where_filter["drawing_type"] = drawing_type
            
            # 搜索向量数据库
            if where_filter:
                results = self.drawings_kb.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where_filter,
                    include=['documents', 'metadatas', 'distances']
                )
            else:
                results = self.drawings_kb.search(query, n_results=top_k)
            
            # 格式化结果
            formatted_results = []
            if results and "results" in results:
                for result in results["results"]:
                    formatted_results.append({
                        "content": result["content"],
                        "metadata": result["metadata"],
                        "similarity": result.get("similarity", 0)
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"❌ 搜索图纸向量数据库失败: {e}")
            return []


# 创建全局服务实例
drawing_service = None

def get_drawing_service() -> DrawingUploadService:
    """获取图纸上传服务实例"""
    global drawing_service
    if drawing_service is None:
        drawing_service = DrawingUploadService()
        # 初始化数据库表
        drawing_service._init_drawings_table()
    return drawing_service 