/**
 * Hook for fetching the list of agents with descriptions.
 *
 * Provides agent names and descriptions for scope configuration
 * in IAM Groups form using searchable select components.
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';


export interface AgentInfo {
  name: string;
  path: string;
  description: string;
}

interface AgentListResponse {
  agents: Array<{
    name: string;
    path: string;
    description?: string;
    [key: string]: unknown;
  }>;
}

interface UseAgentListReturn {
  agents: AgentInfo[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}


export function useAgentList(): UseAgentListReturn {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.get<AgentListResponse>('/api/agents');
      const data = response.data;

      const agentList: AgentInfo[] = (data.agents || []).map((agent) => ({
        name: agent.name,
        path: agent.path,
        description: agent.description || '',
      }));

      // Sort by name
      agentList.sort((a, b) => a.name.localeCompare(b.name));

      setAgents(agentList);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch agents';
      setError(message);
      setAgents([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  return {
    agents,
    isLoading,
    error,
    refetch: fetchAgents,
  };
}
