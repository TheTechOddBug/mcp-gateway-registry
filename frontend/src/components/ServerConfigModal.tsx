import React, { useCallback, useState } from 'react';
import { ClipboardDocumentIcon } from '@heroicons/react/24/outline';
import type { Server } from './ServerCard';
import { useRegistryConfig } from '../hooks/useRegistryConfig';

type IDE = 'vscode' | 'cursor' | 'cline' | 'claude-code';

interface ServerConfigModalProps {
  server: Server;
  isOpen: boolean;
  onClose: () => void;
  onShowToast?: (message: string, type: 'success' | 'error') => void;
}

const ServerConfigModal: React.FC<ServerConfigModalProps> = ({
  server,
  isOpen,
  onClose,
  onShowToast,
}) => {
  const [selectedIDE, setSelectedIDE] = useState<IDE>('vscode');
  const { config: registryConfig, loading: configLoading } = useRegistryConfig();

  // Determine if we're in registry-only mode
  // While config is loading, default to with-gateway behavior (safer default)
  const isRegistryOnly = !configLoading && registryConfig?.deployment_mode === 'registry-only';

  const generateMCPConfig = useCallback(() => {
    const serverName = server.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

    // URL determination with fallback chain:
    // 1. mcp_endpoint (custom override) - always takes precedence
    // 2. proxy_pass_url (in registry-only mode)
    // 3. Constructed gateway URL (default/fallback)
    let url: string;

    if (server.mcp_endpoint) {
      url = server.mcp_endpoint;
    } else if (isRegistryOnly && server.proxy_pass_url) {
      url = server.proxy_pass_url;
    } else {
      const currentUrl = new URL(window.location.origin);
      const baseUrl = `${currentUrl.protocol}//${currentUrl.hostname}`;
      const cleanPath = server.path.replace(/\/+$/, '').replace(/^\/+/, '/');
      url = `${baseUrl}${cleanPath}/mcp`;
    }

    // In registry-only mode, don't include gateway auth headers
    const includeAuthHeaders = !isRegistryOnly;

    switch (selectedIDE) {
      case 'vscode':
        return {
          servers: {
            [serverName]: {
              type: 'http',
              url,
              ...(includeAuthHeaders && {
                headers: {
                  Authorization: 'Bearer [YOUR_AUTH_TOKEN]',
                },
              }),
            },
          },
          ...(includeAuthHeaders && {
            inputs: [
              {
                type: 'promptString',
                id: 'auth-token',
                description: 'Gateway Authentication Token',
              },
            ],
          }),
        };
      case 'cursor':
        return {
          mcpServers: {
            [serverName]: {
              url,
              ...(includeAuthHeaders && {
                headers: {
                  Authorization: 'Bearer [YOUR_AUTH_TOKEN]',
                },
              }),
            },
          },
        };
      case 'cline':
        return {
          mcpServers: {
            [serverName]: {
              type: 'streamableHttp',
              url,
              disabled: false,
              ...(includeAuthHeaders && {
                headers: {
                  Authorization: 'Bearer [YOUR_AUTH_TOKEN]',
                },
              }),
            },
          },
        };
      case 'claude-code':
        return {
          mcpServers: {
            [serverName]: {
              type: 'http',
              url,
              ...(includeAuthHeaders && {
                headers: {
                  Authorization: 'Bearer [YOUR_AUTH_TOKEN]',
                },
              }),
            },
          },
        };
      default:
        return {
          mcpServers: {
            [serverName]: {
              type: 'http',
              url,
              ...(includeAuthHeaders && {
                headers: {
                  Authorization: 'Bearer [YOUR_AUTH_TOKEN]',
                },
              }),
            },
          },
        };
    }
  }, [server.name, server.path, server.proxy_pass_url, server.mcp_endpoint, selectedIDE, isRegistryOnly]);

  const copyConfigToClipboard = useCallback(async () => {
    try {
      const config = generateMCPConfig();
      const configText = JSON.stringify(config, null, 2);
      await navigator.clipboard.writeText(configText);

      onShowToast?.('Configuration copied to clipboard!', 'success');
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      onShowToast?.('Failed to copy configuration', 'error');
    }
  }, [generateMCPConfig, onShowToast]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            MCP Configuration for {server.name}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4">
          <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
              How to use this configuration:
            </h4>
            <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
              <li>Copy the configuration below</li>
              <li>
                Paste it into your <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">mcp.json</code> file
              </li>
              {!isRegistryOnly && (
                <>
                  <li>
                    Replace <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">[YOUR_AUTH_TOKEN]</code> with your
                    gateway authentication token
                  </li>
                  <li>
                    Replace <code className="bg-blue-100 dark:bg-blue-800 px-1 rounded">[YOUR_CLIENT_ID]</code> with your
                    client ID
                  </li>
                </>
              )}
              <li>Restart your AI coding assistant to load the new configuration</li>
            </ol>
          </div>

          {!isRegistryOnly ? (
            <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
              <h4 className="font-medium text-amber-900 dark:text-amber-100 mb-2">Authentication Required</h4>
              <p className="text-sm text-amber-800 dark:text-amber-200">
                This configuration requires gateway authentication tokens. The tokens authenticate your AI assistant with
                the MCP Gateway, not the individual server. Visit the authentication documentation for setup instructions.
              </p>
            </div>
          ) : (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Direct Connection Mode</h4>
              <p className="text-sm text-blue-800 dark:text-blue-200">
                This registry operates in catalog-only mode. The configuration connects directly to the MCP server
                endpoint without going through a gateway proxy.
              </p>
              <p className="text-sm text-blue-800 dark:text-blue-200 mt-2">
                <strong>Note:</strong> The MCP server may still require authentication (API key, auth header, etc.).
                Check the server's documentation to determine if any credentials are needed.
              </p>
            </div>
          )}

          {server.mcp_endpoint && (
            <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg p-4">
              <h4 className="font-medium text-purple-900 dark:text-purple-100 mb-2">Custom Endpoint Configured</h4>
              <p className="text-sm text-purple-800 dark:text-purple-200">
                This server uses a custom MCP endpoint:{' '}
                <code className="bg-purple-100 dark:bg-purple-800 px-1 rounded break-all">{server.mcp_endpoint}</code>
              </p>
            </div>
          )}

          <div className="bg-gray-50 dark:bg-gray-900 border dark:border-gray-700 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 dark:text-white mb-3">Select your IDE/Tool:</h4>
            <div className="flex flex-wrap gap-2">
              {(['vscode', 'cursor', 'cline', 'claude-code'] as IDE[]).map((ide) => (
                <button
                  key={ide}
                  onClick={() => setSelectedIDE(ide)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    selectedIDE === ide
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-600'
                  }`}
                >
                  {ide === 'vscode'
                    ? 'VS Code'
                    : ide === 'cursor'
                    ? 'Cursor'
                    : ide === 'cline'
                    ? 'Cline'
                    : 'Claude Code'}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mt-2">
              Configuration format optimized for{' '}
              {selectedIDE === 'vscode'
                ? 'VS Code'
                : selectedIDE === 'cursor'
                ? 'Cursor'
                : selectedIDE === 'cline'
                ? 'Cline'
                : 'Claude Code'}{' '}
              integration
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-gray-900 dark:text-white">Configuration JSON:</h4>
              <button
                onClick={copyConfigToClipboard}
                className="flex items-center gap-2 px-3 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg transition-colors duration-200"
              >
                <ClipboardDocumentIcon className="h-4 w-4" />
                Copy to Clipboard
              </button>
            </div>
            <pre className="bg-gray-900 text-green-100 p-4 rounded-lg text-sm overflow-x-auto">
              {JSON.stringify(generateMCPConfig(), null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ServerConfigModal;
