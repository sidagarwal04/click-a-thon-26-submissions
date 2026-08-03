/**
 * Where a chat thread gets its Project.
 *
 * Threads belong to a Project, which belongs to a Group. The chat surface
 * deliberately shows neither: someone asking a question about refunds should
 * not first have to invent an organisational hierarchy. So the first visit
 * provisions one and every later visit reuses it.
 *
 * This is a hook rather than a call site so that a Group/Project picker, when
 * one is wanted, replaces the resolution without touching the chat page.
 */

import { useQuery } from '@tanstack/react-query';

import { ApiError, type TokenSource } from '../../api';
import { createGroup, createProject, listGroups, listProjects } from './api';

const DEFAULT_GROUP_NAME = 'Workspace';
const DEFAULT_PROJECT_NAME = 'General';

export const activeProjectKey = ['chat', 'active-project'] as const;

export class ProvisioningDenied extends Error {
  constructor() {
    super(
      'You do not have a project to chat in yet, and your role cannot create one. Ask an owner or admin to add you to a project.',
    );
    this.name = 'ProvisioningDenied';
  }
}

/**
 * Resolve the Project to open Threads in, creating one if the tenant has none.
 *
 * The whole chain lives in a single query so React Query's in-flight dedupe
 * covers it. Two components mounting at once share one resolution rather than
 * racing to create two Groups.
 */
const resolveProjectId = async (getToken: TokenSource): Promise<string> => {
  const groups = await listGroups(getToken);
  // Archived Groups still list; opening new work in one would be surprising.
  const group =
    groups.items.find((candidate) => candidate.archived_at === null) ??
    (await createGroup(getToken, DEFAULT_GROUP_NAME).catch(asDenial));

  const projects = await listProjects(getToken, group.group_id);
  const project = projects.items.find((candidate) => candidate.archived_at === null);
  if (project) return project.project_id;

  // `can_manage` is the server's own answer about this actor, so it is asked
  // rather than inferred from a role — but a viewer who reaches the create
  // anyway gets the same explanation rather than a bare 403.
  if (!group.can_manage) throw new ProvisioningDenied();
  const created = await createProject(getToken, group.group_id, DEFAULT_PROJECT_NAME).catch(
    asDenial,
  );
  return created.project_id;
};

const asDenial = (error: unknown): never => {
  if (error instanceof ApiError && error.status === 403) throw new ProvisioningDenied();
  throw error;
};

export const useActiveProject = (getToken: TokenSource) =>
  useQuery({
    queryKey: activeProjectKey,
    queryFn: () => resolveProjectId(getToken),
    // The answer changes about once per tenant lifetime.
    staleTime: Number.POSITIVE_INFINITY,
    // Retrying a create that already succeeded is how duplicates happen.
    retry: false,
  });
