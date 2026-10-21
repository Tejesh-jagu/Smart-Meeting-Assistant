export function formatAudioTime(seconds) {
  if (!Number.isFinite(seconds)) return '0:00'

  return `${Math.floor(seconds / 60)}:${String(
    Math.floor(seconds % 60)
  ).padStart(2, '0')}`
}


export function makeWavBlob(chunks, inputRate) {
  const inputLength = chunks.reduce((total, chunk) => total + chunk.length, 0)

  if (!inputLength || !inputRate) {
    return new Blob([], { type: 'audio/wav' })
  }

  const input = new Float32Array(inputLength)
  let offset = 0

  for (const chunk of chunks) {
    input.set(chunk, offset)
    offset += chunk.length
  }

  const outputRate = 16000
  const outputLength = Math.floor((inputLength * outputRate) / inputRate)

  if (!outputLength) {
    return new Blob([], { type: 'audio/wav' })
  }

  const buffer = new ArrayBuffer(44 + outputLength * 2)
  const view = new DataView(buffer)

  function writeText(position, value) {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(position + index, value.charCodeAt(index))
    }
  }

  writeText(0, 'RIFF')
  view.setUint32(4, 36 + outputLength * 2, true)
  writeText(8, 'WAVE')
  writeText(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, outputRate, true)
  view.setUint32(28, outputRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeText(36, 'data')
  view.setUint32(40, outputLength * 2, true)

  const ratio = inputRate / outputRate

  for (let index = 0; index < outputLength; index += 1) {
    const position = index * ratio
    const left = Math.floor(position)
    const right = Math.min(left + 1, inputLength - 1)
    const fraction = position - left
    const sample = input[left] * (1 - fraction) + input[right] * fraction
    const clamped = Math.max(-1, Math.min(1, sample))
    const pcm = clamped < 0 ? clamped * 32768 : clamped * 32767

    view.setInt16(44 + index * 2, pcm, true)
  }

  return new Blob([buffer], { type: 'audio/wav' })
}
