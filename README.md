# Ubuntu Desktop Codespace

This repository contains a configuration for a GitHub Codespace that automatically provisions a lightweight Ubuntu desktop environment with GUI capabilities.

## How to Launch the Codespace

1. On the main page of this repository on GitHub, click the green **Code** button.
2. Switch to the **Codespaces** tab.
3. Click the **Create codespace on main** button (or the plus icon).
4. Wait for the environment to build. (The first time you create it, it might take a few minutes as it pulls the Ubuntu image and installs the desktop features).

## Accessing the Environment

You have three main ways to connect to the environment once it is running:

### 1. Directly in Your Web Browser (Easiest)

Once the codespace finishes loading in your browser, a prompt will usually ask if you want to forward ports.
1. Go to the "Ports" tab in the bottom panel of the VS Code web editor.
2. Look for the port labeled **Web UI (noVNC)** (Port `6080`).
3. Hover over the "Local Address" column for that row and click the **Open in Browser** (globe) icon.
4. When prompted, enter the password: `codespaces`

### 2. Via SSH using the GitHub CLI

You can easily connect securely via SSH directly from your local terminal.

1. Ensure you have the GitHub CLI (`gh`) installed on your Fedora machine: `sudo dnf install gh`
2. Authenticate with GitHub: `gh auth login`
3. List your active codespaces: `gh codespace list`
4. Connect via SSH: `gh codespace ssh -c <your-codespace-name>`

### 3. Via VNC (Using Remmina on Fedora)

To use a native VNC client like Remmina, you need to forward the VNC port securely using the GitHub CLI.

1. First, forward the VNC port to your local machine using the GitHub CLI:
   ```bash
   gh codespace ports forward 5901:5901 -c <your-codespace-name>
   ```
   *(Leave this terminal window open while you connect)*
2. Open **Remmina** on your Fedora machine.
3. Create a new connection:
   * Protocol: **VNC - Virtual Network Computing**
   * Server: `localhost:5901`
   * User name: `codespace`
   * Password: `codespaces`
4. Connect!

> **Note:** The desktop environment is lightweight (Fluxbox). Right-click anywhere on the desktop background to open the menu and launch applications or terminals.