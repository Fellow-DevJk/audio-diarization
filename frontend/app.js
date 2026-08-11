const API_BASE_URL = 'http://localhost:8000'

const audioInput = document.querySelector('#audioInput')
const dropZone = document.querySelector('#dropZone')
const selectedFileElement = document.querySelector('#selectedFile')

const analyzeButton = document.querySelector('#analyzeButton')
const clearButton = document.querySelector('#clearButton')
const playButton = document.querySelector('#playButton')

const apiStatus = document.querySelector('#apiStatus')
const requestStatus = document.querySelector('#requestStatus')

const audioPanel = document.querySelector('#audioPanel')
const resultsPanel = document.querySelector('#resultsPanel')
const overlapCard = document.querySelector('#overlapCard')

const currentTimeElement = document.querySelector('#currentTime')
const totalTimeElement = document.querySelector('#totalTime')

const speakerCountElement = document.querySelector('#speakerCount')
const segmentCountElement = document.querySelector('#segmentCount')
const inferenceTimeElement = document.querySelector('#inferenceTime')
const deviceValueElement = document.querySelector('#deviceValue')

const speakerLegend = document.querySelector('#speakerLegend')
const speakerTimeline = document.querySelector('#speakerTimeline')
const segmentsBody = document.querySelector('#segmentsBody')
const overlapList = document.querySelector('#overlapList')

let selectedFile = null
let currentResult = null

const speakerColors = [
  '#3157d5',
  '#0f9f77',
  '#d97706',
  '#8b5cf6',
  '#db2777',
  '#0891b2',
]

const wavesurfer = WaveSurfer.create({
  container: '#waveform',
  height: 120,
  waveColor: '#bac3d3',
  progressColor: '#3157d5',
  cursorColor: '#172033',
  cursorWidth: 2,
  normalize: true,
  dragToSeek: true,
  barWidth: 2,
  barGap: 1,
  barRadius: 2,
})

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) {
    return '00:00.0'
  }

  const safeSeconds = Math.max(0, seconds)
  const minutes = Math.floor(safeSeconds / 60)
  const remainder = safeSeconds % 60

  return `${String(minutes).padStart(2, '0')}:${remainder
    .toFixed(1)
    .padStart(4, '0')}`
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B'
  }

  const units = ['B', 'KB', 'MB', 'GB']
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  )

  const value = bytes / Math.pow(1024, index)

  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function getSpeakerColor(speaker) {
  if (!currentResult) {
    return speakerColors[0]
  }

  const index = currentResult.speakers.indexOf(speaker)

  return speakerColors[
    Math.max(0, index) % speakerColors.length
  ]
}

function setRequestStatus(message, isError = false) {
  requestStatus.textContent = message
  requestStatus.classList.remove('hidden', 'error')

  if (isError) {
    requestStatus.classList.add('error')
  }
}

function clearRequestStatus() {
  requestStatus.textContent = ''
  requestStatus.classList.add('hidden')
  requestStatus.classList.remove('error')
}

async function checkApi() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`)

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()

    apiStatus.textContent =
      `API ready · ${data.device}`

    apiStatus.classList.remove('offline')
    apiStatus.classList.add('online')
  } catch (error) {
    apiStatus.textContent = 'API unavailable'
    apiStatus.classList.remove('online')
    apiStatus.classList.add('offline')
  }
}

async function loadSelectedFile(file) {
  if (!file) {
    return
  }

  selectedFile = file
  currentResult = null

  selectedFileElement.textContent =
    `${file.name} · ${formatBytes(file.size)}`

  selectedFileElement.classList.remove('hidden')

  analyzeButton.disabled = false
  clearButton.disabled = false

  resultsPanel.classList.add('hidden')
  overlapCard.classList.add('hidden')

  clearRequestStatus()

  audioPanel.classList.remove('hidden')

  playButton.disabled = true
  playButton.textContent = 'Play'

  currentTimeElement.textContent = '00:00.0'
  totalTimeElement.textContent = '00:00.0'

  try {
    await wavesurfer.loadBlob(file)

    totalTimeElement.textContent =
      formatTime(wavesurfer.getDuration())

    playButton.disabled = false
  } catch (error) {
    console.error(error)

    setRequestStatus(
      'The browser could not decode this audio file.',
      true,
    )
  }
}

function resetInterface() {
  selectedFile = null
  currentResult = null

  audioInput.value = ''

  selectedFileElement.textContent = ''
  selectedFileElement.classList.add('hidden')

  analyzeButton.disabled = true
  clearButton.disabled = true
  playButton.disabled = true

  audioPanel.classList.add('hidden')
  resultsPanel.classList.add('hidden')
  overlapCard.classList.add('hidden')

  speakerTimeline.innerHTML = ''
  speakerLegend.innerHTML = ''
  segmentsBody.innerHTML = ''
  overlapList.innerHTML = ''

  clearRequestStatus()

  wavesurfer.empty()

  currentTimeElement.textContent = '00:00.0'
  totalTimeElement.textContent = '00:00.0'
}

async function analyzeAudio() {
  if (!selectedFile) {
    return
  }

  analyzeButton.disabled = true
  clearButton.disabled = true

  const originalButtonText = analyzeButton.textContent

  analyzeButton.textContent = 'Analyzing…'

  setRequestStatus(
    'Uploading audio and running speaker diarization…',
  )

  try {
    const formData = new FormData()
    formData.append('audio', selectedFile)

    const response = await fetch(
      `${API_BASE_URL}/diarize`,
      {
        method: 'POST',
        body: formData,
      },
    )

    const body = await response.json()

    if (!response.ok) {
      throw new Error(
        body.detail ||
        `Request failed with status ${response.status}`,
      )
    }

    currentResult = body

    renderResults(body)

    setRequestStatus(
      `Analysis complete in ${body.inference_seconds.toFixed(2)} seconds.`,
    )
  } catch (error) {
    console.error(error)

    setRequestStatus(
      error.message || 'Diarization failed.',
      true,
    )
  } finally {
    analyzeButton.disabled = false
    clearButton.disabled = false
    analyzeButton.textContent = originalButtonText
  }
}

function renderResults(result) {
  speakerCountElement.textContent =
    result.speaker_count

  segmentCountElement.textContent =
    result.segment_count

  inferenceTimeElement.textContent =
    `${result.inference_seconds.toFixed(2)} s`

  deviceValueElement.textContent =
    result.device.toUpperCase()

  renderLegend(result)
  renderTimeline(result)
  renderSegmentsTable(result)
  renderOverlaps(result)

  resultsPanel.classList.remove('hidden')
}

function renderLegend(result) {
  speakerLegend.innerHTML = ''

  for (const speaker of result.speakers) {
    const item = document.createElement('div')
    item.className = 'legend-item'

    const dot = document.createElement('span')
    dot.className = 'legend-dot'
    dot.style.backgroundColor =
      getSpeakerColor(speaker)

    const label = document.createElement('span')
    label.textContent = speaker

    item.append(dot, label)
    speakerLegend.appendChild(item)
  }
}

function renderTimeline(result) {
  speakerTimeline.innerHTML = ''

  const duration =
    wavesurfer.getDuration() ||
    Math.max(
      ...result.segments.map(
        segment => segment.end,
      ),
      1,
    )

  for (const speaker of result.speakers) {
    const row = document.createElement('div')
    row.className = 'timeline-row'

    const label = document.createElement('div')
    label.className = 'timeline-label'
    label.textContent = speaker

    const track = document.createElement('div')
    track.className = 'timeline-track'

    const speakerSegments =
      result.segments.filter(
        segment => segment.speaker === speaker,
      )

    for (const segment of speakerSegments) {
      const block =
        document.createElement('button')

      block.type = 'button'
      block.className = 'timeline-segment'

      block.dataset.start = segment.start
      block.dataset.end = segment.end
      block.dataset.speaker = segment.speaker

      block.style.left =
        `${(segment.start / duration) * 100}%`

      block.style.width =
        `${Math.max(
          ((segment.end - segment.start) /
            duration) *
            100,
          0.15,
        )}%`

      block.style.backgroundColor =
        getSpeakerColor(speaker)

      block.style.color =
        getSpeakerColor(speaker)

      block.title =
        `${speaker}: ` +
        `${formatTime(segment.start)} – ` +
        `${formatTime(segment.end)}`

      block.addEventListener(
        'click',
        () => playSegment(segment),
      )

      track.appendChild(block)
    }

    row.append(label, track)
    speakerTimeline.appendChild(row)
  }

  if (result.overlaps?.length) {
    const row = document.createElement('div')
    row.className = 'timeline-row'

    const label = document.createElement('div')
    label.className = 'timeline-label'
    label.textContent = 'OVERLAP'

    const track = document.createElement('div')
    track.className =
      'timeline-track overlap-track'

    for (const overlap of result.overlaps) {
      const block =
        document.createElement('button')

      block.type = 'button'
      block.className =
        'timeline-segment overlap-segment'

      block.style.left =
        `${(overlap.start / duration) * 100}%`

      block.style.width =
        `${Math.max(
          ((overlap.end - overlap.start) /
            duration) *
            100,
          0.15,
        )}%`

      block.title =
        `Overlap: ${formatTime(overlap.start)} – ` +
        formatTime(overlap.end)

      block.addEventListener('click', () => {
        seekToTime(overlap.start)
      })

      track.appendChild(block)
    }

    row.append(label, track)
    speakerTimeline.appendChild(row)
  }

  const axis = document.createElement('div')
  axis.className = 'timeline-axis'

  axis.appendChild(document.createElement('div'))

  const axisInner = document.createElement('div')
  axisInner.className = 'axis-inner'

  const markers = 5

  for (let index = 0; index <= markers; index++) {
    const marker = document.createElement('span')

    marker.textContent =
      formatTime(
        duration * (index / markers),
      )

    axisInner.appendChild(marker)
  }

  axis.appendChild(axisInner)
  speakerTimeline.appendChild(axis)
}

function renderSegmentsTable(result) {
  segmentsBody.innerHTML = ''

  result.segments.forEach(
    (segment, index) => {
      const row = document.createElement('tr')

      row.className = 'segment-row'
      row.dataset.start = segment.start
      row.dataset.end = segment.end

      row.addEventListener(
        'click',
        () => playSegment(segment),
      )

      const numberCell =
        document.createElement('td')
      numberCell.textContent = index + 1

      const speakerCell =
        document.createElement('td')

      const speakerChip =
        document.createElement('span')
      speakerChip.className = 'speaker-chip'

      const speakerDot =
        document.createElement('span')
      speakerDot.className = 'speaker-chip-dot'
      speakerDot.style.backgroundColor =
        getSpeakerColor(segment.speaker)

      const speakerName =
        document.createElement('span')
      speakerName.textContent = segment.speaker

      speakerChip.append(
        speakerDot,
        speakerName,
      )

      speakerCell.appendChild(speakerChip)

      const startCell =
        document.createElement('td')
      startCell.textContent =
        formatTime(segment.start)

      const endCell =
        document.createElement('td')
      endCell.textContent =
        formatTime(segment.end)

      const durationCell =
        document.createElement('td')
      durationCell.textContent =
        `${(
          segment.end - segment.start
        ).toFixed(2)} s`

      row.append(
        numberCell,
        speakerCell,
        startCell,
        endCell,
        durationCell,
      )

      segmentsBody.appendChild(row)
    },
  )
}

function renderOverlaps(result) {
  overlapList.innerHTML = ''

  if (!result.overlaps?.length) {
    overlapCard.classList.add('hidden')
    return
  }

  for (const overlap of result.overlaps) {
    const item = document.createElement('div')
    item.className = 'overlap-item'

    item.textContent =
      `${formatTime(overlap.start)} – ` +
      `${formatTime(overlap.end)} ` +
      `(${(
        overlap.end - overlap.start
      ).toFixed(2)} s)`

    item.addEventListener('click', () => {
      seekToTime(overlap.start)
    })

    overlapList.appendChild(item)
  }

  overlapCard.classList.remove('hidden')
}

function seekToTime(seconds) {
  const duration = wavesurfer.getDuration()

  if (!duration) {
    return
  }

  wavesurfer.seekTo(
    Math.min(
      Math.max(seconds / duration, 0),
      1,
    ),
  )
}

async function playSegment(segment) {
  seekToTime(segment.start)

  try {
    await wavesurfer.play(
      segment.start,
      segment.end,
    )
  } catch (error) {
    console.error(error)
  }
}

function updateActiveSegment(currentTime) {
  document
    .querySelectorAll(
      '.timeline-segment[data-start]',
    )
    .forEach(element => {
      const start =
        Number(element.dataset.start)
      const end =
        Number(element.dataset.end)

      element.classList.toggle(
        'active',
        currentTime >= start &&
        currentTime <= end,
      )
    })

  document
    .querySelectorAll('.segment-row')
    .forEach(row => {
      const start =
        Number(row.dataset.start)
      const end =
        Number(row.dataset.end)

      row.classList.toggle(
        'active',
        currentTime >= start &&
        currentTime <= end,
      )
    })
}

audioInput.addEventListener('change', event => {
  const file = event.target.files?.[0]

  if (file) {
    loadSelectedFile(file)
  }
})

dropZone.addEventListener('dragover', event => {
  event.preventDefault()
  dropZone.classList.add('dragging')
})

dropZone.addEventListener('dragleave', () => {
  dropZone.classList.remove('dragging')
})

dropZone.addEventListener('drop', event => {
  event.preventDefault()
  dropZone.classList.remove('dragging')

  const file = event.dataTransfer.files?.[0]

  if (file) {
    loadSelectedFile(file)
  }
})

analyzeButton.addEventListener(
  'click',
  analyzeAudio,
)

clearButton.addEventListener(
  'click',
  resetInterface,
)

playButton.addEventListener(
  'click',
  async () => {
    await wavesurfer.playPause()
  },
)

wavesurfer.on('ready', duration => {
  totalTimeElement.textContent =
    formatTime(duration)

  playButton.disabled = false
})

wavesurfer.on('timeupdate', currentTime => {
  currentTimeElement.textContent =
    formatTime(currentTime)

  updateActiveSegment(currentTime)
})

wavesurfer.on('play', () => {
  playButton.textContent = 'Pause'
})

wavesurfer.on('pause', () => {
  playButton.textContent = 'Play'
})

wavesurfer.on('finish', () => {
  playButton.textContent = 'Play'
})

checkApi()
