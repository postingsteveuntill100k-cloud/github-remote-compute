import asyncio
import os
import io
import json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

# Define the scopes required for Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive']

# Initialize the MCP Server
app = Server("google-drive-tool")

def get_drive_service():
    """Authenticates and returns the Google Drive API service."""
    # Look for the credentials file
    creds_file = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    if not os.path.exists(creds_file):
        raise FileNotFoundError(f"Credentials file not found at {creds_file}. Set GOOGLE_APPLICATION_CREDENTIALS environment variable or place credentials.json in the current directory.")

    creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    service = build('drive', 'v3', credentials=creds)
    return service

@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_files",
            description="List files in Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional search query (e.g., \"name='example.txt'\")"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)",
                        "default": 10
                    }
                }
            }
        ),
        types.Tool(
            name="upload_file",
            description="Upload a local file to Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "Path to the local file to upload"
                    },
                    "drive_filename": {
                        "type": "string",
                        "description": "Name to give the file in Google Drive"
                    }
                },
                "required": ["local_path", "drive_filename"]
            }
        ),
        types.Tool(
            name="download_file",
            description="Download a file from Google Drive to the local machine",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file in Google Drive to download"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Path where the file should be saved locally"
                    }
                },
                "required": ["file_id", "local_path"]
            }
        ),
        types.Tool(
            name="delete_file",
            description="Delete a file from Google Drive",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The ID of the file in Google Drive to delete"
                    }
                },
                "required": ["file_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        service = get_drive_service()
    except Exception as e:
        return [types.TextContent(type="text", text=f"Authentication Error: {str(e)}")]

    try:
        if name == "list_files":
            query = arguments.get("query")
            limit = arguments.get("limit", 10)

            results = service.files().list(
                q=query, pageSize=limit, fields="nextPageToken, files(id, name, mimeType)"
            ).execute()
            items = results.get('files', [])

            if not items:
                return [types.TextContent(type="text", text="No files found.")]
            else:
                output = "Files:\n"
                for item in items:
                    output += f"- {item['name']} (ID: {item['id']}, Type: {item['mimeType']})\n"
                return [types.TextContent(type="text", text=output)]

        elif name == "upload_file":
            local_path = arguments["local_path"]
            drive_filename = arguments["drive_filename"]

            if not os.path.exists(local_path):
                return [types.TextContent(type="text", text=f"Error: Local file not found: {local_path}")]

            file_metadata = {'name': drive_filename}
            import mimetypes
            mime_type, _ = mimetypes.guess_type(local_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'

            media = MediaIoBaseUpload(io.FileIO(local_path, 'rb'), mimetype=mime_type, resumable=True)

            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return [types.TextContent(type="text", text=f"File uploaded successfully. File ID: {file.get('id')}")]

        elif name == "download_file":
            file_id = arguments["file_id"]
            local_path = arguments["local_path"]

            request = service.files().get_media(fileId=file_id)
            with io.FileIO(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()

            return [types.TextContent(type="text", text=f"File downloaded successfully to {local_path}")]

        elif name == "delete_file":
            file_id = arguments["file_id"]
            service.files().delete(fileId=file_id).execute()
            return [types.TextContent(type="text", text=f"File ID {file_id} deleted successfully.")]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"API Error: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
