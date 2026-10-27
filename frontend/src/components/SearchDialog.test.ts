import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SearchDialog from './SearchDialog.vue'
import type { Item } from '../api'

vi.mock('../api', () => ({ searchTmdb: vi.fn(async () => []) }))

const item = {
  id: 1,
  source_path: '/inbox/Show.S01E01.mkv',
  media_type: 'tv',
  title: 'Show',
  year: null,
  candidates: [{ tmdb_id: 1, media_type: 'tv', title: 'Show', original_title: 'Show', year: 2020, overview: '', poster_path: null }],
} as unknown as Item

let root: HTMLElement | null = null

async function mount(props: { item: Item; count?: number }) {
  root = document.createElement('div')
  document.body.appendChild(root)
  createApp(SearchDialog, props).mount(root)
  await nextTick()
  return root
}

afterEach(() => {
  root?.remove()
  root = null
})

describe('SearchDialog', () => {
  it('單筆時顯示檔名', async () => {
    const el = await mount({ item })
    expect(el.textContent).toContain('Show.S01E01.mkv')
    expect(el.textContent).not.toContain('將套用到')
  })

  it('count 為 1 時視為單筆', async () => {
    const el = await mount({ item, count: 1 })
    expect(el.textContent).toContain('Show.S01E01.mkv')
  })

  it('多筆時顯示套用數量', async () => {
    const el = await mount({ item, count: 5 })
    expect(el.textContent).toContain('將套用到已選取的 5 個項目')
    expect(el.textContent).not.toContain('Show.S01E01.mkv')
  })
})
