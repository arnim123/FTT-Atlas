import { build } from 'esbuild';
import { mkdtemp, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export async function bundleTestModule(source, name = 'api') {
  const folder = await mkdtemp(join(tmpdir(), 'atlas-tests-'));
  const output = join(folder, `${name}.mjs`);
  const result = await build({
    stdin: { contents: source, resolveDir: process.cwd(), loader: 'tsx' },
    bundle: true, platform: 'node', format: 'esm', write: false,
    tsconfig: resolve('tsconfig.json'),
    alias: { '@dnd-kit/core': resolve('src/lib/dnd-fallback.tsx') },
    define: { 'import.meta.env': JSON.stringify({ MODE: 'test', VITE_USE_MOCKS: 'true', DEV: true }), 'process.env.NODE_ENV': '"production"' },
    banner: { js: "import { createRequire as atlasCreateRequire } from 'node:module'; const require = atlasCreateRequire(import.meta.url);" },
    logLevel: 'silent',
  });
  await writeFile(output, result.outputFiles[0].contents);
  return import(pathToFileURL(output).href);
}
