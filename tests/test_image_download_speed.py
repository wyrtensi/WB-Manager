
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import time

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Need to mock Flask app context if needed, but the function returns jsonify which needs app context
# Or we can just mock jsonify.

from flask import Flask
app = Flask(__name__)

# We need to import main after mocking things it imports, or patch them where they are used.
# main.py imports db, wb_api at module level.

with patch('database.database_manager.DatabaseManager') as MockDB, \
     patch('api.wb_api.WildberriesAPI') as MockAPI:
    import main
    from models import Goods

def test_background_download_speed():
    # Mock DB instance
    mock_db = MagicMock()
    main.db = mock_db

    # Mock Goods
    g1 = Goods(item_uid="1", buyer_sid="123", scanned_code="1", encoded_scanned_code="1",
               vendor_code="100", cell="1", status="GOODS_READY",
               price=100, price_with_sale=90, is_paid=1, priority_order=0,
               payment_type="card", info=None, sticker_code="1", barcode="1", is_on_way=False)

    mock_db.get_all_goods_by_buyer.return_value = [g1]

    # Mock wb_api instance
    mock_wb_api = MagicMock()
    mock_wb_api.download_image_sync.return_value = (Path("somepath"), True) # Downloaded = True
    main.wb_api = mock_wb_api

    # Reset active_downloads
    main.active_downloads = set()

    with app.test_request_context(json={'type': 'all'}):
        with patch('main.time.sleep') as mock_sleep:
            with patch('threading.Thread') as mock_thread:
                # Run task immediately
                def side_effect(target, daemon):
                    target()
                    return MagicMock()
                mock_thread.side_effect = side_effect

                # Call API
                main.api_buyer_cache_images("123")

                # Verify
                mock_wb_api.download_image_sync.assert_called_with("100", 1, 'small', force=False)
                mock_sleep.assert_called_with(0.2)

def test_background_download_skip_speed():
    mock_db = MagicMock()
    main.db = mock_db

    g1 = Goods(item_uid="1", buyer_sid="123", scanned_code="1", encoded_scanned_code="1",
               vendor_code="100", cell="1", status="GOODS_READY",
               price=100, price_with_sale=90, is_paid=1, priority_order=0,
               payment_type="card", info=None, sticker_code="1", barcode="1", is_on_way=False)

    mock_db.get_all_goods_by_buyer.return_value = [g1]

    mock_wb_api = MagicMock()
    # Mock return path
    mock_path = MagicMock(spec=Path)
    mock_path.exists.return_value = True
    mock_wb_api.download_image_sync.return_value = (mock_path, False) # Downloaded = False
    main.wb_api = mock_wb_api

    main.active_downloads = set()

    with app.test_request_context(json={'type': 'all'}):
        with patch('main.time.sleep') as mock_sleep:
            with patch('threading.Thread') as mock_thread:
                def side_effect(target, daemon):
                    target()
                    return MagicMock()
                mock_thread.side_effect = side_effect

                main.api_buyer_cache_images("123")

                mock_sleep.assert_called_with(0.02)

if __name__ == "__main__":
    test_background_download_speed()
    test_background_download_skip_speed()
    print("Tests passed!")
