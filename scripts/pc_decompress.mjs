// pc_decompress.mjs — .pc/.df LZSS 解压（FANUC 同款：FE EF 00 01 + U32BE 长度 + 流）
// 复用 ai-robot-backup-checker 的 tpParser.decompressLzss（40/40 实测算法）
// Usage: node pc_decompress.mjs <out_dir> <file1> [file2 ...]
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { basename, join } from 'node:path'
import { pathToFileURL } from 'node:url'

const { decompressLzss, isCompressedTp, readU32BE } = await import(
  pathToFileURL('D:/ai-robot-backup-checker/src/shared/tpParser.js').href)

const [outDir, ...files] = process.argv.slice(2)
mkdirSync(outDir, { recursive: true })

for (const f of files) {
  const buf = new Uint8Array(readFileSync(f))
  const name = basename(f)
  try {
    if (!isCompressedTp(buf)) {
      console.log(`${name}: NOT LZSS (no FE EF 00 01)`)
      continue
    }
    const declared = readU32BE(buf, 4)
    const out = decompressLzss(buf.subarray(8), declared)
    const outPath = join(outDir, name + '.dec')
    writeFileSync(outPath, out)
    // 可读串统计
    const text = Buffer.from(out).toString('latin1')
    const runs = text.match(/[\x20-\x7e]{5,}/g) || []
    console.log(`${name}: ${buf.length}B -> ${out.length}B (declared ${declared})  strings=${runs.length}  -> ${outPath}`)
  } catch (e) {
    console.log(`${name}: FAIL ${e.message}`)
  }
}
