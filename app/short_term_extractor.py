# app/short_term_extractor.py
"""
Module để trích xuất và phân loại thông tin từ chat message sử dụng LLM

Chức năng:
1. Trích xuất intent từ message
2. Phân loại keywords
3. Xác định file_path, function_name nếu liên quan đến code
4. Tạo embedding vector cho similarity search
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from openai import OpenAI
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class ShortTermMemoryExtractor:
    """
    Sử dụng LLM để trích xuất và phân loại thông tin từ chat message
    """
    
    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model
        self.vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
        
    async def extract_message_info(self, 
                                 content: str, 
                                 role: str,
                                 project_id: str,
                                 conversation_id: str) -> Dict:
        """
        Trích xuất thông tin từ message sử dụng LLM
        
        Args:
            content: Nội dung message
            role: Vai trò (user, assistant, system)
            project_id: ID dự án
            conversation_id: ID cuộc trò chuyện
            
        Returns:
            Dict chứa thông tin đã trích xuất
        """
        try:
            # 1. Trích xuất intent
            intent = await self._extract_intent(content, role)
            
            # 2. Trích xuất keywords
            keywords = await self._extract_keywords(content)
            
            # 3. Phân tích code context (nếu có)
            code_info = await self._analyze_code_context(content)
            
            # 4. Tạo embedding
            embedding = await self._create_embedding(content)
            
            return {
                "intent": intent,
                "keywords": keywords,
                "file_path": code_info.get("file_path"),
                "function_name": code_info.get("function_name"),
                "line_start": code_info.get("line_start"),
                "line_end": code_info.get("line_end"),
                "embedding": embedding,
                "ttl": self._calculate_ttl(intent, role)
            }
            
        except Exception as e:
            logger.error(f"Error extracting message info: {e}")
            # Fallback values
            return {
                "intent": "unknown",
                "keywords": [],
                "file_path": None,
                "function_name": None,
                "line_start": None,
                "line_end": None,
                "embedding": await self._create_embedding(content),
                "ttl": 3600  # 1 hour default
            }
    
    async def _extract_intent(self, content: str, role: str) -> str:
        """Trích xuất intent của message"""
        prompt = f"""
        Phân tích message sau và xác định intent chính:
        
        Role: {role}
        Content: {content}
        
        Các loại intent có thể có:
        - question: Câu hỏi, yêu cầu thông tin
        - request: Yêu cầu thực hiện hành động
        - explanation: Giải thích, hướng dẫn
        - code_review: Review code, tìm lỗi
        - bug_report: Báo cáo lỗi
        - feature_request: Yêu cầu tính năng mới
        - clarification: Làm rõ, xác nhận
        - greeting: Chào hỏi
        - goodbye: Chào tạm biệt
        - other: Khác
        
        Chỉ trả về 1 từ khóa intent, không giải thích thêm.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=50
            )
            return response.choices[0].message.content.strip().lower()
        except Exception as e:
            logger.error(f"Error extracting intent: {e}")
            return "unknown"
    
    async def _extract_keywords(self, content: str) -> List[str]:
        """Trích xuất keywords từ content"""
        prompt = f"""
        Trích xuất 5-10 từ khóa quan trọng nhất từ message sau:
        
        Content: {content}
        
        Chỉ trả về danh sách từ khóa, mỗi từ khóa trên 1 dòng, không đánh số.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=100
            )
            
            keywords_text = response.choices[0].message.content.strip()
            keywords = [kw.strip() for kw in keywords_text.split('\n') if kw.strip()]
            return keywords[:10]  # Limit to 10 keywords
            
        except Exception as e:
            logger.error(f"Error extracting keywords: {e}")
            return []
    
    async def _analyze_code_context(self, content: str) -> Dict:
        """Phân tích xem message có liên quan đến code không và AI có chỉnh sửa code không"""
        prompt = f"""
        Phân tích message sau và xác định thông tin code nếu có. Đặc biệt chú ý nếu AI đã chỉnh sửa code:
        
        Content: {content}
        
        Trả về JSON với các trường:
        - file_path: Đường dẫn file nếu được đề cập (ví dụ: "src/auth.py")
        - function_name: Tên function nếu được đề cập (ví dụ: "login_user")
        - line_start: Số dòng bắt đầu của code được AI chỉnh sửa
        - line_end: Số dòng kết thúc của code được AI chỉnh sửa
        - code_changes: Object chứa chi tiết thay đổi code nếu AI đã chỉnh sửa, bao gồm:
          - change_type: "added", "modified", "deleted", "refactored"
          - old_code: Code cũ (nếu có)
          - new_code: Code mới (nếu có)
          - description: Mô tả thay đổi
        
        Nếu không có thông tin code hoặc AI không chỉnh sửa code, trả về {{}}.
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Try to parse JSON
            try:
                result = json.loads(result_text)
                return {
                    "file_path": result.get("file_path"),
                    "function_name": result.get("function_name"),
                    "line_start": result.get("line_start"),
                    "line_end": result.get("line_end"),
                    "code_changes": result.get("code_changes")
                }
            except json.JSONDecodeError:
                return {}
                
        except Exception as e:
            logger.error(f"Error analyzing code context: {e}")
            return {}
    
    async def _create_embedding(self, content: str) -> List[float]:
        """Tạo embedding vector cho content"""
        try:
            # Sử dụng OpenAI embedding
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=content
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            # Fallback: tạo embedding đơn giản bằng TF-IDF
            return self._create_simple_embedding(content)
    
    def _create_simple_embedding(self, content: str) -> List[float]:
        """Tạo embedding đơn giản bằng TF-IDF (fallback)"""
        try:
            # Fit vectorizer với content
            tfidf_matrix = self.vectorizer.fit_transform([content])
            embedding = tfidf_matrix.toarray()[0]
            
            # Normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
                
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Error creating simple embedding: {e}")
            # Return zero vector as last resort
            return [0.0] * 100
    
    def _calculate_ttl(self, intent: str, role: str) -> int:
        """Tính toán TTL dựa trên intent và role"""
        # TTL trong giây
        base_ttl = {
            "question": 3600,      # 1 hour
            "request": 7200,       # 2 hours
            "explanation": 10800,  # 3 hours
            "code_review": 14400,  # 4 hours
            "bug_report": 18000,   # 5 hours
            "feature_request": 21600,  # 6 hours
            "clarification": 1800, # 30 minutes
            "greeting": 300,       # 5 minutes
            "goodbye": 300,        # 5 minutes
            "other": 3600          # 1 hour default
        }
        
        # Assistant messages có TTL cao hơn
        multiplier = 1.5 if role == "assistant" else 1.0
        
        return int(base_ttl.get(intent, 3600) * multiplier)
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Tính độ tương đồng giữa 2 embedding"""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1).reshape(1, -1)
            vec2 = np.array(embedding2).reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(vec1, vec2)[0][0]
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0


# Global instance
_extractor_instance = None

def get_extractor() -> ShortTermMemoryExtractor:
    """Get global extractor instance"""
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = ShortTermMemoryExtractor()
    return _extractor_instance


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_extractor():
        extractor = ShortTermMemoryExtractor()
        
        # Test message
        content = "Tôi muốn thêm chức năng đăng nhập vào file auth.py, function login_user ở dòng 25-30"
        role = "user"
        project_id = "test_project"
        conversation_id = "conv_001"
        
        result = await extractor.extract_message_info(
            content=content,
            role=role,
            project_id=project_id,
            conversation_id=conversation_id
        )
        
        print("Extracted info:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(test_extractor())
