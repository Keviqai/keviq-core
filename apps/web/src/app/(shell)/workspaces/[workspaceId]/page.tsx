'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  useWorkspaces,
  useTaskList,
  useArtifactList,
  usePendingApprovalCount,
} from '@keviq/server-state';
import {
  taskNewPath,
  tasksPath,
  artifactsPath,
  approvalsPath,
} from '@keviq/routing';
import { primaryButtonStyle } from '@/modules/shared/ui-styles';
import { DemoCTACard } from '@/modules/workspace/demo-cta-card';
import { HomeSection } from './_components/home-section';
import { HomeTaskCard } from './_components/home-task-card';
import { HomeArtifactRow } from './_components/home-artifact-row';

const ACTIVE_STATUSES = new Set(['pending', 'running', 'waiting_approval']);
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'cancelled']);

export default function WorkspaceOverview() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = params.workspaceId;
  const { data: workspaces } = useWorkspaces();
  const { data: taskData, isLoading: tasksLoading } = useTaskList(workspaceId);
  const { data: artifactData } = useArtifactList(workspaceId);
  const { data: approvalCountData } = usePendingApprovalCount(workspaceId);

  const workspace = workspaces?.find((ws) => ws.id === workspaceId);
  const allTasks = taskData?.items ?? [];
  const pendingApprovals = approvalCountData?.pending_count ?? 0;

  // Group tasks by lifecycle
  const draftTasks = allTasks.filter((t) => t.task_status === 'draft');
  const activeTasks = allTasks.filter((t) => ACTIVE_STATUSES.has(t.task_status));
  const completedTasks = allTasks.filter((t) => TERMINAL_STATUSES.has(t.task_status));
  const recentArtifacts = (artifactData?.items ?? []).slice(0, 5);

  const isEmpty = !tasksLoading && allTasks.length === 0;

  return (
    <div>
      {/* Header with New Task CTA */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
          {workspace?.display_name ?? 'Workspace'}
        </h1>
        <Link
          href={taskNewPath(workspaceId)}
          style={{
            ...primaryButtonStyle,
            padding: '10px 20px',
            fontSize: 14,
            textDecoration: 'none',
          }}
        >
          + New Task
        </Link>
      </div>

      {/* Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
        <StatCard label="Drafts" value={draftTasks.length} href={tasksPath(workspaceId)} loading={tasksLoading} />
        <StatCard
          label="Active"
          value={activeTasks.length}
          href={tasksPath(workspaceId)}
          loading={tasksLoading}
          highlight={activeTasks.length > 0}
          highlightColor="#1e40af"
        />
        <StatCard
          label="Completed"
          value={completedTasks.length}
          href={tasksPath(workspaceId)}
          loading={tasksLoading}
          highlight={completedTasks.length > 0}
          highlightColor="#059669"
        />
        <StatCard
          label="Pending Approvals"
          value={pendingApprovals}
          href={approvalsPath(workspaceId) + '?decision=pending'}
          highlight={pendingApprovals > 0}
          highlightColor="#d97706"
        />
      </div>

      {/* Demo CTA for empty workspace */}
      {isEmpty && (
        <div style={{ marginBottom: 24 }}>
          <DemoCTACard workspaceId={workspaceId} />
        </div>
      )}

      {/* Sections */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* Drafts */}
        {(draftTasks.length > 0 || (!tasksLoading && !isEmpty)) && (
          <HomeSection
            title="Your Drafts"
            viewAllHref={tasksPath(workspaceId)}
            isEmpty={draftTasks.length === 0}
            emptyText="No drafts. Click '+ New Task' to start one."
          >
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
              {draftTasks.slice(0, 6).map((task) => (
                <HomeTaskCard key={task.task_id} task={task} workspaceId={workspaceId} />
              ))}
            </div>
          </HomeSection>
        )}

        {/* Active Tasks */}
        {activeTasks.length > 0 && (
          <HomeSection title="Active Tasks" viewAllHref={tasksPath(workspaceId)}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
              {activeTasks.slice(0, 6).map((task) => (
                <HomeTaskCard key={task.task_id} task={task} workspaceId={workspaceId} />
              ))}
            </div>
          </HomeSection>
        )}

        {/* Completed (only if no drafts/active to fill the page) */}
        {completedTasks.length > 0 && draftTasks.length === 0 && activeTasks.length === 0 && (
          <HomeSection title="Recent Tasks" viewAllHref={tasksPath(workspaceId)}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
              {completedTasks.slice(0, 6).map((task) => (
                <HomeTaskCard key={task.task_id} task={task} workspaceId={workspaceId} />
              ))}
            </div>
          </HomeSection>
        )}

        {/* Recent Outputs */}
        <HomeSection
          title="Recent Outputs"
          viewAllHref={artifactsPath(workspaceId)}
          isEmpty={recentArtifacts.length === 0}
          emptyText="No outputs yet. Outputs will appear here after tasks complete."
        >
          <div>
            {recentArtifacts.map((a) => (
              <HomeArtifactRow key={a.id} artifact={a} workspaceId={workspaceId} />
            ))}
          </div>
        </HomeSection>
      </div>
    </div>
  );
}

// ── Stat Card ────────────────────────────────────────────────

function StatCard({
  label,
  value,
  href,
  loading,
  highlight,
  highlightColor,
}: {
  label: string;
  value: number;
  href: string;
  loading?: boolean;
  highlight?: boolean;
  highlightColor?: string;
}) {
  return (
    <Link href={href} style={{ textDecoration: 'none', color: 'inherit' }}>
      <div style={{ padding: 16, border: '1px solid #e5e7eb', borderRadius: 8 }}>
        <h3 style={{ fontSize: 13, color: '#6b7280', marginBottom: 6, marginTop: 0 }}>{label}</h3>
        <p style={{
          fontSize: 28,
          fontWeight: 700,
          margin: 0,
          color: highlight ? highlightColor : '#111827',
        }}>
          {loading ? '…' : value}
        </p>
      </div>
    </Link>
  );
}
