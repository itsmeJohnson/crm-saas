// Phase 3.1 architecture-guard: the generic CRM-Core frontend layer must never
// import Dental-specific modules. The ONLY place allowed to reference
// pages/dental/* or components/dental/* is the composition root
// (routes/moduleRegistry.ts), which lazily code-splits every industry module.
//
// This test statically scans the core store + core-domain component directories
// and fails if any of them imports from a dental path. It keeps the import
// direction Industry -> Core and stops a Core file from reaching into Dental.
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const SRC = join(here, '..', '..'); // frontend/src

// Core / generic domain directories that must stay dental-free.
const CORE_DIRS = [
  'store',
  'components/leads',
  'components/crm',
  'components/customers',
  'components/tasks',
  'components/calendar',
  'components/communications',
];

const DENTAL_IMPORT = /from\s+['"][^'"]*(?:pages|components)\/dental[^'"]*['"]/;

function walk(dir: string): string[] {
  let out: string[] = [];
  let entries: string[];
  try {
    entries = readdirSync(dir);
  } catch {
    return out;
  }
  for (const name of entries) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) {
      out = out.concat(walk(full));
    } else if (/\.(ts|tsx)$/.test(name) && !/\.test\.(ts|tsx)$/.test(name)) {
      out.push(full);
    }
  }
  return out;
}

describe('architecture boundary: Core frontend must not import Dental', () => {
  const files = CORE_DIRS.flatMap((d) => walk(join(SRC, d)));

  it('collects core-domain source files to scan', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it('no core store/component imports from pages/dental or components/dental', () => {
    const offenders: string[] = [];
    for (const f of files) {
      const text = readFileSync(f, 'utf8');
      if (DENTAL_IMPORT.test(text)) {
        offenders.push(relative(SRC, f));
      }
    }
    expect(offenders, `Core files importing Dental: ${offenders.join(', ')}`).toEqual([]);
  });
});
