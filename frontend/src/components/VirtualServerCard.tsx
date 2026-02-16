import React, { useState } from 'react';
import {
  PencilIcon,
  TrashIcon,
  ClipboardDocumentIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
import { VirtualServerInfo } from '../types/virtualServer';


/**
 * Props for the VirtualServerCard component.
 */
interface VirtualServerCardProps {
  virtualServer: VirtualServerInfo;
  canModify: boolean;
  onToggle: (path: string, enabled: boolean) => void;
  onEdit: (server: VirtualServerInfo) => void;
  onDelete: (path: string) => void;
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
}


/**
 * VirtualServerCard renders a dashboard card for a virtual MCP server.
 *
 * Uses a teal/cyan gradient for visual distinction from regular ServerCard.
 * Displays server name, description, tool count, backend count, and backend paths.
 */
const VirtualServerCard: React.FC<VirtualServerCardProps> = ({
  virtualServer: server,
  canModify,
  onToggle,
  onEdit,
  onDelete,
  onShowToast,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopyEndpoint = async () => {
    const endpointUrl = `${window.location.origin}${server.path}`;
    try {
      await navigator.clipboard.writeText(endpointUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      onShowToast?.('Endpoint URL copied to clipboard', 'success');
    } catch {
      onShowToast?.('Failed to copy endpoint URL', 'error');
    }
  };

  return (
    <div className="group rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 h-full flex flex-col bg-gradient-to-br from-teal-50 to-cyan-50 dark:from-teal-900/20 dark:to-cyan-900/20 border-2 border-teal-200 dark:border-teal-700 hover:border-teal-300 dark:hover:border-teal-600">
      {/* Header */}
      <div className="p-5 pb-4">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-lg font-bold text-gray-900 dark:text-white truncate">
                {server.server_name}
              </h3>
              <span className="px-2 py-0.5 text-xs font-semibold bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-300 rounded-full flex-shrink-0 border border-teal-200 dark:border-teal-600">
                VIRTUAL
              </span>
            </div>

            <code className="text-xs text-gray-600 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 px-2 py-1 rounded font-mono">
              {server.path}
            </code>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            {canModify && (
              <button
                className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-lg transition-all duration-200"
                onClick={() => onEdit(server)}
                title="Edit virtual server"
              >
                <PencilIcon className="h-4 w-4" />
              </button>
            )}

            <button
              onClick={handleCopyEndpoint}
              className="p-2 text-gray-400 hover:text-teal-600 dark:hover:text-teal-300 hover:bg-teal-50 dark:hover:bg-teal-700/50 rounded-lg transition-all duration-200"
              title="Copy endpoint URL"
            >
              {copied ? (
                <CheckIcon className="h-4 w-4 text-green-500" />
              ) : (
                <ClipboardDocumentIcon className="h-4 w-4" />
              )}
            </button>

            {canModify && (
              <button
                onClick={() => onDelete(server.path)}
                className="p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-700/50 rounded-lg transition-all duration-200"
                title="Delete virtual server"
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <p className="text-gray-600 dark:text-gray-300 text-sm leading-relaxed line-clamp-2 mb-4">
          {server.description || 'No description available'}
        </p>

        {/* Tags */}
        {server.tags && server.tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-4">
            {server.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="px-2 py-1 text-xs font-medium bg-teal-50 dark:bg-teal-900/30 text-teal-700 dark:text-teal-300 rounded"
              >
                #{tag}
              </span>
            ))}
            {server.tags.length > 3 && (
              <span className="px-2 py-1 text-xs font-medium bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded">
                +{server.tags.length - 3}
              </span>
            )}
          </div>
        )}

        {/* Backend paths */}
        {server.backend_paths && server.backend_paths.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {server.backend_paths.slice(0, 4).map((bp) => (
              <span
                key={bp}
                className="px-2 py-0.5 text-xs font-mono bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded"
              >
                {bp}
              </span>
            ))}
            {server.backend_paths.length > 4 && (
              <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded">
                +{server.backend_paths.length - 4} more
              </span>
            )}
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="px-5 pb-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
            <div className="p-1.5 bg-teal-50 dark:bg-teal-900/30 rounded">
              <svg className="h-4 w-4 text-teal-600 dark:text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.42 15.17l-5.59-5.59m0 0L4.24 8.59m1.59.99h12.34M12.58 8.83l5.59 5.59m0 0l1.59.99m-1.59-.99H5.83" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold">{server.tool_count}</div>
              <div className="text-xs">Tools</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-gray-600 dark:text-gray-300">
            <div className="p-1.5 bg-cyan-50 dark:bg-cyan-900/30 rounded">
              <svg className="h-4 w-4 text-cyan-600 dark:text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold">{server.backend_count}</div>
              <div className="text-xs">Backends</div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="mt-auto px-5 py-4 border-t border-teal-100 dark:border-teal-800 bg-teal-50/50 dark:bg-teal-900/10 rounded-b-2xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${
              server.is_enabled
                ? 'bg-green-400 shadow-lg shadow-green-400/30'
                : 'bg-gray-300 dark:bg-gray-600'
            }`} />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {server.is_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>

          {/* Toggle Switch */}
          {canModify && (
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={server.is_enabled}
                onChange={(e) => onToggle(server.path, e.target.checked)}
                className="sr-only peer"
                aria-label={`Enable ${server.server_name}`}
              />
              <div className={`relative w-12 h-6 rounded-full transition-colors duration-200 ease-in-out ${
                server.is_enabled
                  ? 'bg-teal-600'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}>
                <div className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform duration-200 ease-in-out ${
                  server.is_enabled ? 'translate-x-6' : 'translate-x-0'
                }`} />
              </div>
            </label>
          )}
        </div>
      </div>
    </div>
  );
};

export default VirtualServerCard;
