import type { DemoVideoItem } from '../types/runtime'

const IGNORED_TOKENS = new Set(['demo', 'session', 'video', 'rgb', 'stream', 'clip'])

function tokenize(value: string | null | undefined): string[] {
  if (!value) {
    return []
  }
  const stem = value
    .replace(/\\/g, '/')
    .split('/')
    .pop()
    ?.replace(/\.[a-z0-9]+$/i, '') ?? ''
  return stem
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .split('_')
    .filter(Boolean)
    .filter((token) => !IGNORED_TOKENS.has(token))
    .filter((token) => !/^cam\d+$/i.test(token))
}

export function mediaKey(value: string | null | undefined): string {
  return tokenize(value).join('_')
}

export function matchDemoVideo(
  demoVideos: ReadonlyArray<DemoVideoItem>,
  candidates: Array<string | null | undefined>,
): DemoVideoItem | null {
  const resolved = candidates
    .map((candidate) => ({
      raw: candidate ?? '',
      key: mediaKey(candidate),
    }))
    .filter((item) => item.raw || item.key)

  for (const item of demoVideos) {
    const itemKey = mediaKey(item.filename || item.name)
    for (const candidate of resolved) {
      const rawName = candidate.raw.replace(/\\/g, '/').split('/').pop() ?? ''
      const rawStem = rawName.replace(/\.[a-z0-9]+$/i, '')
      if (rawName && (item.filename === rawName || item.name === rawStem)) {
        return item
      }
      if (candidate.key && itemKey && candidate.key === itemKey) {
        return item
      }
      if (candidate.key && itemKey && (candidate.key.startsWith(itemKey) || itemKey.startsWith(candidate.key))) {
        return item
      }
    }
  }
  return null
}
