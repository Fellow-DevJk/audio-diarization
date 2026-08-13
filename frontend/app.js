const BROKER_URL = window.APP_CONFIG.brokerUrl
const MAX_UPLOAD_BYTES = window.APP_CONFIG.maxUploadBytes
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

const previewReportButton = document.querySelector('#previewReportButton')
const downloadReportButton = document.querySelector('#downloadReportButton')
const printReportButton = document.querySelector('#printReportButton')
const reportModal = document.querySelector('#reportModal')
const reportPreview = document.querySelector('#reportPreview')
const closeReportButton = document.querySelector('#closeReportButton')

const audioDurationElement = document.querySelector('#audioDuration')
const realTimeFactorElement = document.querySelector('#realTimeFactor')
const overlapSummaryElement = document.querySelector('#overlapSummary')
const speakerStatsElement = document.querySelector('#speakerStats')

let selectedFile = null
let currentResult = null
let currentReportUrl = null

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

  const totalTenths = Math.round(
    Math.max(0, seconds) * 10
  )

  const minutes = Math.floor(
    totalTenths / 600
  )

  const remainingTenths =
    totalTenths % 600

  const wholeSeconds = Math.floor(
    remainingTenths / 10
  )

  const tenths =
    remainingTenths % 10

  return (
    `${String(minutes).padStart(2, '0')}:` +
    `${String(wholeSeconds).padStart(2, '0')}.` +
    `${tenths}`
  )
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
    const response = await fetch(
      `${BROKER_URL}/health`
    )

    if (!response.ok) {
      throw new Error(
        `HTTP ${response.status}`
      )
    }

    apiStatus.textContent =
      'AWS backend ready'

    apiStatus.classList.remove(
      'offline'
    )

    apiStatus.classList.add(
      'online'
    )
  } catch (error) {
    console.error(error)

    apiStatus.textContent =
      'AWS backend unavailable'

    apiStatus.classList.remove(
      'online'
    )

    apiStatus.classList.add(
      'offline'
    )
  }
}

async function loadSelectedFile(file) {
  if (!file) {
    return
  }

  selectedFile = file
  currentResult = null

  disableReportActions()
  closeReportPreview()

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
  disableReportActions()
  closeReportPreview()
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

async function requestUploadUrl(file) {
  const response = await fetch(
    `${BROKER_URL}/upload-url`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          'application/json',
      },
      body: JSON.stringify({
        filename: file.name,
        size_bytes: file.size,
      }),
    },
  )

  const body =
    await response.json()

  if (!response.ok) {
    throw new Error(
      body.error ||
      'Could not create upload URL.',
    )
  }

  return body
}


async function uploadAudioToS3(
  file,
  uploadUrl,
  contentType,
) {
  const response = await fetch(
    uploadUrl,
    {
      method: 'PUT',
      headers: {
        'Content-Type':
          contentType,
      },
      body: file,
    },
  )

  if (!response.ok) {
    throw new Error(
      `Audio upload failed ` +
      `(${response.status}).`,
    )
  }
}


async function startAsyncInference(
  inputKey,
  contentType,
) {
  const response = await fetch(
    `${BROKER_URL}/invoke`,
    {
      method: 'POST',
      headers: {
        'Content-Type':
          'application/json',
      },
      body: JSON.stringify({
        input_key: inputKey,
        content_type: contentType,
      }),
    },
  )

  const body =
    await response.json()

  if (!response.ok) {
    throw new Error(
      body.error ||
      'Could not start diarization.',
    )
  }

  return body
}


function sleep(milliseconds) {
  return new Promise(
    resolve =>
      setTimeout(
        resolve,
        milliseconds,
      ),
  )
}


async function waitForInference(
  outputLocation,
  failureLocation,
) {
  const pollIntervalMs = 3000
  const maxAttempts = 200

  for (
    let attempt = 1;
    attempt <= maxAttempts;
    attempt++
  ) {
    setRequestStatus(
      `Processing audio… ` +
      `(check ${attempt})`,
    )

    const response = await fetch(
      `${BROKER_URL}/result`,
      {
        method: 'POST',
        headers: {
          'Content-Type':
            'application/json',
        },
        body: JSON.stringify({
          output_location:
            outputLocation,
          failure_location:
            failureLocation,
        }),
      },
    )

    const rawBody = await response.text()

    let body

    try {
      body = JSON.parse(rawBody)
    } catch {
      throw new Error(
        `Backend returned HTTP ${response.status}: ` +
        (rawBody || 'empty response')
      )
    }

    if (
      response.ok &&
      body.status === 'completed'
    ) {
      return body.result
    }

    if (
      body.status === 'failed'
    ) {
      throw new Error(
        body.error ||
        'Diarization failed.',
      )
    }

    if (
      response.status !== 202 &&
      !response.ok
    ) {
      throw new Error(
        body.error ||
        `Result check failed ` +
        `(${response.status}).`,
      )
    }

    await sleep(
      pollIntervalMs
    )
  }

  throw new Error(
    'Diarization timed out.'
  )
}

function disableReportActions() {
  previewReportButton.disabled = true
  downloadReportButton.disabled = true
  printReportButton.disabled = true
}

function enableReportActions() {
  previewReportButton.disabled = false
  downloadReportButton.disabled = false
  printReportButton.disabled = false
}

function revokeCurrentReportUrl() {
  if (currentReportUrl) {
    URL.revokeObjectURL(
      currentReportUrl
    )

    currentReportUrl = null
  }
}

function closeReportPreview() {
  reportModal.classList.add(
    'hidden'
  )

  reportPreview.src = ''

  revokeCurrentReportUrl()
}

async function previewCurrentReport() {
  if (
    !currentResult ||
    !selectedFile
  ) {
    return
  }

  revokeCurrentReportUrl()

  const blob =
    await window.DiarizationReport
      .createBlob(
        currentResult,
        selectedFile,
      )

  currentReportUrl =
    URL.createObjectURL(blob)

  reportPreview.src = currentReportUrl

  reportModal.classList.remove(
    'hidden'
  )
}

async function downloadCurrentReport() {
  if (
    !currentResult ||
    !selectedFile
  ) {
    return
  }

  await window.DiarizationReport
    .download(
      currentResult,
      selectedFile,
    )
}

async function printCurrentReport() {
  if (
    !currentResult ||
    !selectedFile
  ) {
    return
  }

  revokeCurrentReportUrl()

  const blob =
    await window.DiarizationReport
      .createBlob(
        currentResult,
        selectedFile,
      )

  currentReportUrl =
    URL.createObjectURL(blob)

  const printWindow =
    window.open(
      currentReportUrl,
      '_blank',
    )

  if (!printWindow) {
    setRequestStatus(
      'The browser blocked the report window.',
      true,
    )
  }
}

async function analyzeAudio() {
  if (
    selectedFile.size > MAX_UPLOAD_BYTES
  ) {
    setRequestStatus(
      `Maximum demo file size is ` +
      `${formatBytes(
        MAX_UPLOAD_BYTES
      )}.`,
      true,
    )

    return
  }
  if (!selectedFile) {
    return
  }

  analyzeButton.disabled = true
  clearButton.disabled = true

  const originalButtonText =
    analyzeButton.textContent

  analyzeButton.textContent =
    'Analyzing…'

  try {
    setRequestStatus(
      'Preparing secure upload…'
    )

    const uploadInfo =
      await requestUploadUrl(
        selectedFile
      )

    setRequestStatus(
      'Uploading audio to AWS…'
    )

    await uploadAudioToS3(
      selectedFile,
      uploadInfo.upload_url,
      uploadInfo.content_type,
    )

    setRequestStatus(
      'Starting GPU diarization…'
    )

    const inference =
      await startAsyncInference(
        uploadInfo.input_key,
        uploadInfo.content_type,
      )

    setRequestStatus(
      'Running diarization on GPU…'
    )

    const result =
      await waitForInference(
        inference.output_location,
        inference.failure_location,
      )

    currentResult = result

    renderResults(result)
    enableReportActions()
    setRequestStatus(
      `Analysis complete in ` +
      `${result.inference_seconds.toFixed(2)} ` +
      `seconds on ` +
      `${result.device.toUpperCase()}.`,
    )
  } catch (error) {
    console.error(error)

    setRequestStatus(
      error.message ||
      'Diarization failed.',
      true,
    )
  } finally {
    analyzeButton.disabled = false
    clearButton.disabled = false

    analyzeButton.textContent =
      originalButtonText
  }
}

function renderResults(result) {
  speakerCountElement.textContent =
    result.speaker_count

  segmentCountElement.textContent =
    result.segment_count

  audioDurationElement.textContent =
  formatTime(result.audio_duration_seconds)

  realTimeFactorElement.textContent =
    result.real_time_factor !== null
      ? `${result.real_time_factor.toFixed(2)}x`
      : '—'

  overlapSummaryElement.textContent =
    `${result.overlap_count} · ` +
    `${result.overlap_seconds.toFixed(2)} s`

  inferenceTimeElement.textContent =
    `${result.inference_seconds.toFixed(2)} s`

  deviceValueElement.textContent =
    result.device.toUpperCase()

  renderSpeakerStats(result)
  renderLegend(result)
  renderTimeline(result)
  renderSegmentsTable(result)
  renderOverlaps(result)

  resultsPanel.classList.remove('hidden')
}

function renderSpeakerStats(result) {
  speakerStatsElement.innerHTML = ''

  for (const speaker of result.speakers) {
    const stats = result.speaker_stats[speaker]

    const card = document.createElement('div')
    card.className = 'speaker-stat-card'

    const header = document.createElement('div')
    header.className = 'speaker-stat-header'

    const identity = document.createElement('div')
    identity.className = 'speaker-chip'

    const dot = document.createElement('span')
    dot.className = 'speaker-chip-dot'
    dot.style.backgroundColor =
      getSpeakerColor(speaker)

    const name = document.createElement('strong')
    name.textContent = speaker

    identity.append(dot, name)

    const percentage =
      document.createElement('strong')

    percentage.textContent =
      `${stats.speaking_percentage.toFixed(1)}%`

    header.append(identity, percentage)

    const bar = document.createElement('div')
    bar.className = 'speaker-stat-bar'

    const fill = document.createElement('div')
    fill.className = 'speaker-stat-fill'

    fill.style.width =
      `${Math.min(
        stats.speaking_percentage,
        100,
      )}%`

    fill.style.backgroundColor =
      getSpeakerColor(speaker)

    bar.appendChild(fill)

    const details = document.createElement('div')
    details.className = 'speaker-stat-details'

    details.innerHTML = `
      <span>
        Speaking:
        <strong>${formatTime(stats.speaking_seconds)}</strong>
      </span>

      <span>
        Segments:
        <strong>${stats.segment_count}</strong>
      </span>
    `

    card.append(
      header,
      bar,
      details,
    )

    speakerStatsElement.appendChild(card)
  }
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

previewReportButton.addEventListener(
  'click',
  previewCurrentReport,
)

downloadReportButton.addEventListener(
  'click',
  downloadCurrentReport,
)

printReportButton.addEventListener(
  'click',
  printCurrentReport,
)

closeReportButton.addEventListener(
  'click',
  closeReportPreview,
)

reportModal.addEventListener(
  'click',
  event => {
    if (
      event.target ===
      reportModal
    ) {
      closeReportPreview()
    }
  },
)

document.addEventListener(
  'keydown',
  event => {
    if (
      event.key === 'Escape' &&
      !reportModal.classList
        .contains('hidden')
    ) {
      closeReportPreview()
    }
  },
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
