"""
MCP server (CareerViet) — wrapper mỏng trên code crawl có sẵn.
Không sửa bất kỳ file gốc nào.

Cài đặt (1 lần):
    pip install mcp[cli]

Debug / test:
    cd "Crawl ngành x cấp bậc x địa điểm"
    python -m mcp dev crawler_mcp/careerviet_server.py

Đưa vào Claude Code (thêm vào .claude/settings.json):
    {
      "mcpServers": {
        "careerviet": {
          "command": "python",
          "args": [
            "C:\\\\Users\\\\bach.pham\\\\OneDrive\\\\Crawl CRV\\\\Crawl ngành x cấp bậc x địa điểm\\\\crawler_mcp\\\\careerviet_server.py"
          ]
        }
      }
    }
"""
import sys
import os
from typing import Optional

# Thêm project root vào sys.path để import careerviet/, config.py
# File này: <root>/crawler_mcp/careerviet_server.py  → dirname 2 lần = root
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mcp.server.fastmcp import FastMCP

from careerviet.auth import get_session as _crv_get_session
from careerviet.mappings import fetch_industries, fetch_locations, fetch_levels
from careerviet.crawler import _post


# ─── MCP server ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    "careerviet",
    instructions=(
        "Tra cứu số lượng CV ứng viên trên CareerViet theo ngành nghề × địa điểm × cấp bậc. "
        "Workflow: (1) gọi crv_list_* để lấy ID, (2) gọi crv_get_count để lấy số liệu. "
        "Probe pattern hiệu quả: gọi crv_get_count không có level_id trước — "
        "nếu count=0 thì không cần gọi tiếp theo từng cấp bậc."
    ),
)


# ─── Lazy session (không block khi import) ───────────────────────────────────

_session = None


def _get_session():
    """Lazy-load session. Raise RuntimeError với hướng dẫn nếu cookie hết hạn."""
    global _session
    if _session is None:
        try:
            _session = _crv_get_session()
        except SystemExit:
            # careerviet/auth.py gọi sys.exit(1) khi cookie hết hạn
            raise RuntimeError(
                "Cookie CareerViet hết hạn hoặc không tìm thấy. "
                "Chạy 'py careerviet/setup_cookies.py' rồi restart MCP server."
            )
    return _session


# ─── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def crv_list_industries() -> list[dict]:
    """
    Trả về danh sách ngành nghề có sẵn trên CareerViet (lấy từ API live).

    Returns:
        list[{"id": int, "name": str}]

    Ví dụ kết quả:
        [{"id": 24, "name": "Công nghệ thông tin"}, {"id": 4, "name": "Tiếp thị / Marketing"}, ...]

    Dùng `id` làm tham số `industry_id` trong crv_get_count().
    """
    try:
        return fetch_industries(_get_session())
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Không lấy được danh sách ngành: {e}")


@mcp.tool()
def crv_list_locations() -> list[dict]:
    """
    Trả về danh sách địa điểm (tỉnh / thành phố) tại Việt Nam trên CareerViet.

    Returns:
        list[{"id": int, "name": str}]

    Ví dụ kết quả:
        [{"id": 8, "name": "Hồ Chí Minh"}, {"id": 1, "name": "Hà Nội"}, {"id": 17, "name": "Đà Nẵng"}, ...]

    Dùng `id` làm tham số `location_id` trong crv_get_count().
    Lưu ý: Đã lọc country_id=1 — chỉ trả về địa điểm Việt Nam.
    """
    try:
        return fetch_locations(_get_session())
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Không lấy được danh sách địa điểm: {e}")


@mcp.tool()
def crv_list_levels() -> list[dict]:
    """
    Trả về danh sách cấp bậc trên CareerViet (lấy từ API live).

    Returns:
        list[{"id": int, "name": str}]

    Ví dụ kết quả:
        [{"id": 1, "name": "Intern"}, {"id": 2, "name": "Nhân viên"}, {"id": 3, "name": "Trưởng nhóm"}, ...]

    Dùng `id` làm tham số `level_id` trong crv_get_count().
    Truyền level_id=None (mặc định) để lấy tổng không phân cấp bậc.
    """
    try:
        return fetch_levels(_get_session())
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Không lấy được danh sách cấp bậc: {e}")


@mcp.tool()
def crv_get_count(
    industry_id: int,
    location_id: int,
    level_id: Optional[int] = None,
) -> dict:
    """
    Tra số lượng CV ứng viên trên CareerViet theo ngành × địa điểm (× cấp bậc tùy chọn).

    Args:
        industry_id: ID ngành nghề từ crv_list_industries().
                     Ví dụ: 24 (Công nghệ thông tin), 4 (Tiếp thị / Marketing).
        location_id: ID địa điểm từ crv_list_locations().
                     Ví dụ: 8 (Hồ Chí Minh), 1 (Hà Nội), 17 (Đà Nẵng).
        level_id:    ID cấp bậc từ crv_list_levels() — tùy chọn.
                     None (mặc định) = không lọc cấp bậc, trả tổng (dùng làm "probe").
                     Nếu tổng = 0 → bỏ qua các cấp bậc, không cần gọi thêm.

    Returns:
        {
          "count":       int,       # số CV khớp filter
          "industry_id": int,
          "location_id": int,
          "level_id":    int|None,  # None = tổng (không lọc cấp bậc)
        }

    Ví dụ:
        crv_get_count(24, 8)        → tổng CV ngành IT ở HCM (mọi cấp bậc)
        crv_get_count(24, 8, 2)     → CV ngành IT ở HCM cấp Nhân viên
        crv_get_count(4, 1, None)   → tổng CV ngành Marketing ở Hà Nội
    """
    body: dict = {
        "industry_ids": [industry_id],
        "location_ids": [{"location_id": location_id}],
        "limit":   1,
        "order":   "desc",
        "sort_by": "",
    }
    if level_id is not None:
        body["level_id"] = level_id

    try:
        count = _post(_get_session(), body)
        return {
            "count":       count if count is not None else 0,
            "industry_id": industry_id,
            "location_id": location_id,
            "level_id":    level_id,
        }
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Không lấy được count (industry={industry_id}, location={location_id}, "
            f"level={level_id}): {e}. "
            "Nếu lỗi do auth: chạy 'py careerviet/setup_cookies.py' rồi restart server."
        )


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()  # mặc định: stdio transport — phù hợp cho Claude Desktop / Claude Code
