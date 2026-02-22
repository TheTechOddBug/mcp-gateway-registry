import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

// ─── Types ──────────────────────────────────────────────────────

export interface IAMGroup {
  name: string;
  description?: string;
  path?: string;
  members_count?: number;
}

export interface IAMUser {
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  groups?: string[];
  enabled?: boolean;
  is_admin?: boolean;
  account_type?: string;
  serviceAccountsEnabled?: boolean;
}

export interface M2MCredentials {
  client_id: string;
  client_secret: string;
  name: string;
}

export interface CreateHumanUserPayload {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  password?: string;
  groups?: string[];
}

export interface CreateM2MPayload {
  name: string;
  description?: string;
  groups?: string[];
}

export interface CreateGroupPayload {
  name: string;
  description?: string;
  // scope_config is included for future backend support.
  // Currently the backend accepts but does not process it.
  scope_config?: Record<string, unknown>;
}

// ─── Hook: useIAMGroups ─────────────────────────────────────────

export function useIAMGroups() {
  const [groups, setGroups] = useState<IAMGroup[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGroups = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.get('/api/management/iam/groups');
      setGroups(res.data.groups || res.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load groups');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchGroups(); }, [fetchGroups]);

  return { groups, isLoading, error, refetch: fetchGroups };
}

export async function createGroup(payload: CreateGroupPayload): Promise<any> {
  const res = await axios.post('/api/management/iam/groups', payload);
  return res.data;
}

export async function deleteGroup(name: string): Promise<void> {
  await axios.delete(`/api/management/iam/groups/${encodeURIComponent(name)}`);
}

// ─── Group Detail Types & Functions ────────────────────────────

export interface GroupDetail {
  id: string;
  name: string;
  path?: string;
  description?: string;
  server_access?: Array<{server: string; methods: string[]; tools?: string[]}>;
  group_mappings?: string[];
  ui_permissions?: Record<string, string[]>;
  agent_access?: string[];
}

export interface UpdateGroupPayload {
  description?: string;
  scope_config?: {
    server_access?: Array<{server: string; methods: string[]; tools?: string[]}>;
    ui_permissions?: Record<string, string[]>;
    agent_access?: string[];
  };
}

export async function getGroup(groupName: string): Promise<GroupDetail> {
  const res = await axios.get(`/api/management/iam/groups/${encodeURIComponent(groupName)}`);
  return res.data;
}

export async function updateGroup(
  groupName: string,
  payload: UpdateGroupPayload
): Promise<GroupDetail> {
  const res = await axios.patch(
    `/api/management/iam/groups/${encodeURIComponent(groupName)}`,
    payload
  );
  return res.data;
}

// ─── Hook: useIAMUsers ──────────────────────────────────────────

export function useIAMUsers(search?: string) {
  const [users, setUsers] = useState<IAMUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { limit: 500 };
      if (search) params.search = search;
      const res = await axios.get('/api/management/iam/users', { params });
      setUsers(res.data.users || res.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load users');
    } finally {
      setIsLoading(false);
    }
  }, [search]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  return { users, isLoading, error, refetch: fetchUsers };
}

export async function createHumanUser(payload: CreateHumanUserPayload): Promise<any> {
  const res = await axios.post('/api/management/iam/users/human', payload);
  return res.data;
}

export async function createM2MAccount(payload: CreateM2MPayload): Promise<M2MCredentials> {
  const res = await axios.post('/api/management/iam/users/m2m', payload);
  return res.data;
}

export async function deleteUser(username: string): Promise<void> {
  await axios.delete(`/api/management/iam/users/${encodeURIComponent(username)}`);
}

export interface UpdateUserGroupsResponse {
  username: string;
  groups: string[];
  added: string[];
  removed: string[];
}

export async function updateUserGroups(
  username: string,
  groups: string[]
): Promise<UpdateUserGroupsResponse> {
  const res = await axios.patch(
    `/api/management/iam/users/${encodeURIComponent(username)}/groups`,
    { groups }
  );
  return res.data;
}
