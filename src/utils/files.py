import os

try:
    from utils.utils import call_go_get_viam_dot_dir
except ModuleNotFoundError:
    # when running as local module with run.sh
    from ..utils.utils import call_go_get_viam_dot_dir

def capture_dir(pass_id: str) -> str:
    capture_dir = os.path.join(call_go_get_viam_dot_dir(), 'capture', pass_id)
    os.makedirs(capture_dir, exist_ok=True)
    return capture_dir