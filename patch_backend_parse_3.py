import re
import os

with open("/app/mcp_server.py", "r") as f:
    content = f.read()

# I see it fell back to the mocked array, let's print the exception to see why

old_upload = """            else:
                raise ValueError("No data found")
        except Exception as e:
            log.warning(f"Failed to parse uploaded file: {e}")"""

new_upload = """            else:
                raise ValueError("No data found")
        except Exception as e:
            import traceback
            log.warning(f"Failed to parse uploaded file: {e} - Traceback: {traceback.format_exc()}")"""

content = content.replace(old_upload, new_upload)

with open("/app/mcp_server.py", "w") as f:
    f.write(content)
