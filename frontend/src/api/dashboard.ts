import { db } from '@/mocks/db';
import type { Dashboard, User } from '@/types';
import { isAdmin } from '@/lib/access';
import { USE_MOCKS, request } from './client';
import { filteredDocuments } from './documents';
import * as live from './live';

export function getDashboard(actor: User): Promise<Dashboard> {
  if (!USE_MOCKS) return live.getDashboard();
  return request(() => {
    const docs = filteredDocuments(actor);
    const month = new Date().toISOString().slice(0, 7);
    const since = Date.now() - 30 * 86400000;
    const calls = db.audit.filter(event => (isAdmin(actor) || event.userId === actor.id) && Date.parse(event.time) >= since);
    const agentSparkline = Array.from({ length: 14 }, (_, index) => {
      const start = Date.now() - (14 - index) * 86400000;
      return calls.filter(event => { const time = Date.parse(event.time); return time >= start && time < start + 86400000; }).length;
    });
    return { totalDocuments: docs.length, addedThisMonth: docs.filter(d => d.createdAt.startsWith(month)).length,
      activeUsers: db.users.filter(u => u.status === 'active' && (isAdmin(actor) || u.departmentId === actor.departmentId)).length,
      byDepartment: db.departments.map(dept => ({ name: dept.name, count: docs.filter(d => d.departmentId === dept.id).length, color: dept.color ?? '#4a8b78' })),
      recent: docs.slice(0, 5), popular: [...docs].sort((a, b) => b.views - a.views).slice(0, 5),
      previousMonth: docs.filter(d => !d.createdAt.startsWith(month)).length,
      agentCalls30d: calls.length, agentSparkline,
    };
  });
}
