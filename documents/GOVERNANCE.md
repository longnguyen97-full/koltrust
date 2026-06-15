# Security Và Data Governance

## Hiện Trạng

Project đã có một số điểm bảo vệ cơ bản:

- API keys được đọc từ biến môi trường hoặc `.env`, không hard-code vào code.
- `.env` được giữ local và không nên commit.
- Comment text và author identifier có thể được hash trong release build.
- Dataset chỉ dùng public fields từ YouTube/TikTok.
- Có `data_dictionary.md` mô tả schema và ý nghĩa cột.
- Có `dataset_stats.json` và `manifest.json` để mô tả lần build dataset.
- Có MinIO chạy chung trong Docker stack để mô phỏng object storage/data lake local.
- Có Pandera quality gate trước khi publish dữ liệu.

## Phần Còn Thiếu So Với Production

Chưa có governance/security đầy đủ:

- Chưa có authentication/authorization cho FastAPI.
- Chưa có secret manager như Vault, AWS Secrets Manager hoặc GCP Secret Manager.
- Chưa có data catalog như Apache Atlas hoặc DataHub.
- Chưa có lineage tự động từ raw đến bronze/silver/gold.
- Chưa có RBAC cho dataset/API.
- Chưa có policy retention/xóa dữ liệu.
- Chưa có audit log truy cập dữ liệu.
- Chưa có masking/tokenization policy chuẩn hóa cho PII.

## Đề Xuất Production

Nếu triển khai production, nên bổ sung:

- Secret manager để quản lý API keys.
- FastAPI auth bằng OAuth2/JWT hoặc API gateway.
- Data catalog để quản lý metadata, owner, lineage, quality score.
- Data retention policy cho raw data và comments.
- RBAC theo vai trò: data engineer, analyst, admin.
- Audit log cho truy cập API và dataset.
- Data classification: public, internal, sensitive.
- Data quality gate bắt buộc trước khi publish sang serving layer.
