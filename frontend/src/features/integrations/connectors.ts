import { API_BASE_URL, MCP_SERVER_URL, OPENAPI_URL } from '@/lib/constants';

export function connectorGuides(base = API_BASE_URL): ConnectorGuide[] {
  const root = base.replace(/\/$/, '');
  const mcp = root.includes('example') ? MCP_SERVER_URL : `${root}/mcp`;
  const openApi = root.includes('example') ? OPENAPI_URL : `${root}/api/v1/agent/openapi.json`;
  return guideList(mcp, openApi, root);
}

export interface ConnectorGuide {
  id: string;
  name: string;
  summary: string;
  auth: 'oauth' | 'token' | 'rest';
  steps: string[];
  snippets: { label: string; value: string }[];
  openApiUrl?: string;
  consentPreview?: string;
}

const tokenHeader = 'Authorization: Bearer TOKEN';

function guideList(mcp: string, openApi: string, root: string): ConnectorGuide[] {
  return [
  {
    id: 'chatgpt', name: 'ChatGPT', auth: 'oauth', summary: 'Add Company Knowledge as a custom connector. ChatGPT signs in with your Google account.',
    steps: ['Open Settings → Connectors / Apps', 'Create a custom connector', 'Set authentication to OAuth', 'Paste the MCP URL', 'Sign in with Google', 'Allow'],
    consentPreview: '/oauth/consent?app=ChatGPT&redirect_uri=https://chatgpt.com/connector_platform_oauth_redirect&verified=1',
    snippets: [{ label: 'MCP URL', value: mcp }],
  },
  {
    id: 'claude', name: 'Claude', auth: 'oauth', summary: 'Add Company Knowledge as a custom connector. Claude signs in with your Google account.',
    steps: ['Open Settings → Connectors', 'Choose Add custom connector', 'Paste the MCP URL', 'Sign in with Google', 'Allow'],
    consentPreview: '/oauth/consent?app=Claude&redirect_uri=https://claude.ai/api/mcp/auth_callback&verified=1',
    snippets: [{ label: 'MCP URL', value: mcp }],
  },
  {
    id: 'grok', name: 'Grok', auth: 'token', summary: 'Point Grok at the MCP server and send a personal access token.',
    steps: ['Create a personal access token', 'Add the MCP server URL in Grok', `Set the header ${tokenHeader}`, 'Replace TOKEN with your token'],
    snippets: [{ label: 'Grok MCP config', value: `${tokenHeader}\n\n{\n  "mcp_servers": {\n    "company_knowledge": {\n      "url": "${mcp}",\n      "headers": { "Authorization": "Bearer TOKEN" }\n    }\n  }\n}` }],
  },
  {
    id: 'cursor', name: 'Cursor / Claude Code', auth: 'token', summary: 'Paste a token-based MCP config into Cursor or Claude Code.',
    steps: ['Create a personal access token', 'In Cursor, open Settings → MCP and paste the Cursor snippet', 'For Claude Code, add the Claude Code snippet to your MCP config', 'Replace TOKEN with your token', 'Reload the MCP servers'],
    snippets: [
      { label: 'Cursor', value: `{\n  "mcpServers": {\n    "company-knowledge": {\n      "url": "${mcp}",\n      "headers": { "Authorization": "Bearer TOKEN" }\n    }\n  }\n}` },
      { label: 'Claude Code', value: `{\n  "mcpServers": {\n    "company-knowledge": {\n      "type": "http",\n      "url": "${mcp}",\n      "headers": { "Authorization": "Bearer TOKEN" }\n    }\n  }\n}` },
    ],
  },
  {
    id: 'custom', name: 'Custom / REST API', auth: 'rest', summary: 'Call the REST API from your own bot with a personal access token.',
    steps: ['Create a personal access token', 'Open the OpenAPI description', `Call the REST API with ${tokenHeader}`, 'Replace TOKEN with your token'],
    openApiUrl: openApi,
    snippets: [{ label: 'curl example', value: `curl "${root}/api/v1/agent/search?q=Inventory" \\\n  -H "Authorization: Bearer TOKEN"` }],
  },
  ];
}

export const connectors = connectorGuides();
