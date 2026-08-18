(function () {
  const REPORT_TITLE =
    'Speaker Diarization Analysis Report'

  const SPEAKER_COLORS = [
    [49, 87, 213],
    [15, 159, 119],
    [217, 119, 6],
    [139, 92, 246],
    [219, 39, 119],
    [8, 145, 178],
  ]

  function safeNumber(value, fallback = 0) {
    return Number.isFinite(Number(value))
      ? Number(value)
      : fallback
  }

  function formatSeconds(seconds) {
    const value =
      Math.max(0, safeNumber(seconds))

    const minutes =
      Math.floor(value / 60)

    const remaining =
      value - minutes * 60

    return (
      `${String(minutes).padStart(2, '0')}:` +
      `${remaining.toFixed(2).padStart(5, '0')}`
    )
  }

  function baseFilename(filename) {
    const value =
      filename || 'audio'

    const lastDot =
      value.lastIndexOf('.')

    return lastDot > 0
      ? value.slice(0, lastDot)
      : value
  }

  function getSpeakerColor(
    result,
    speaker,
  ) {
    const index =
      Math.max(
        0,
        (result.speakers || [])
          .indexOf(speaker),
      )

    return SPEAKER_COLORS[
      index % SPEAKER_COLORS.length
    ]
  }

  function addPageHeader(
    doc,
    subtitle,
  ) {
    doc.setTextColor(
      15,
      23,
      42,
    )

    doc.setFont(
      'helvetica',
      'bold',
    )

    doc.setFontSize(18)

    doc.text(
      REPORT_TITLE,
      14,
      18,
    )

    doc.setFont(
      'helvetica',
      'normal',
    )

    doc.setFontSize(9)

    doc.setTextColor(
      100,
      116,
      139,
    )

    doc.text(
      subtitle,
      14,
      24,
    )

    doc.setDrawColor(
      203,
      213,
      225,
    )

    doc.line(
      14,
      28,
      196,
      28,
    )
  }

  function addFooter(doc) {
    const pages =
      doc.internal.getNumberOfPages()

    for (
      let page = 1;
      page <= pages;
      page++
    ) {
      doc.setPage(page)

      doc.setFontSize(8)

      doc.setTextColor(
        100,
        116,
        139,
      )

      doc.text(
        `Page ${page} of ${pages}`,
        196,
        287,
        {
          align: 'right',
        },
      )

      doc.text(
        'Automated diarization output — not a speaker identity determination.',
        14,
        287,
      )
    }
  }

  function drawMetric(
    doc,
    x,
    y,
    width,
    label,
    value,
  ) {
    doc.setFillColor(
      248,
      250,
      252,
    )

    doc.setDrawColor(
      226,
      232,
      240,
    )

    doc.roundedRect(
      x,
      y,
      width,
      20,
      2,
      2,
      'FD',
    )

    doc.setFontSize(8)
    doc.setFont(
      'helvetica',
      'normal',
    )
    doc.setTextColor(
      100,
      116,
      139,
    )

    doc.text(
      label,
      x + 4,
      y + 6,
    )

    doc.setFontSize(13)
    doc.setFont(
      'helvetica',
      'bold',
    )
    doc.setTextColor(
      15,
      23,
      42,
    )

    doc.text(
      String(value),
      x + 4,
      y + 15,
    )
  }

  function drawSpeakerTimeline(
    doc,
    result,
    startY,
  ) {
    const speakers =
      result.speakers || []

    const segments =
      result.segments || []

    const overlaps =
      result.overlaps || []

    const latestSegmentEnd =
      Math.max(
        0,
        ...(result.segments || [])
          .map(segment =>
            safeNumber(segment.end)
          ),
      )

    const latestOverlapEnd =
      Math.max(
        0,
        ...(result.overlaps || [])
          .map(overlap =>
            safeNumber(overlap.end)
          ),
      )

    const duration =
      Math.max(
        0.001,
        safeNumber(
          result.audio_duration_seconds,
        ),
        latestSegmentEnd,
        latestOverlapEnd,
      )

    const left = 42
    const right = 196
    const width = right - left
    const rowHeight = 10

    doc.setFontSize(11)
    doc.setFont(
      'helvetica',
      'bold',
    )
    doc.setTextColor(
      15,
      23,
      42,
    )

    doc.text(
      'Speaker activity timeline',
      14,
      startY,
    )

    let y =
      startY + 8

    for (
      let index = 0;
      index < speakers.length;
      index++
    ) {
      const speaker =
        speakers[index]

      const color =
        getSpeakerColor(
          result,
          speaker,
        )

      doc.setFontSize(8)
      doc.setFont(
        'helvetica',
        'bold',
      )

      doc.setTextColor(
        51,
        65,
        85,
      )

      doc.text(
        speaker,
        14,
        y + 5,
      )

      doc.setFillColor(
        241,
        245,
        249,
      )

      doc.rect(
        left,
        y,
        width,
        7,
        'F',
      )

      for (
        const segment of segments
      ) {
        if (
          segment.speaker !== speaker
        ) {
          continue
        }

        const start =
          safeNumber(
            segment.start,
          )

        const end =
          safeNumber(
            segment.end,
          )

        const x =
          left +
          (start / duration) *
            width

        const segmentWidth =
          Math.max(
            0.5,
            (
              (end - start) /
              duration
            ) * width,
          )

        doc.setFillColor(
          color[0],
          color[1],
          color[2],
        )

        doc.rect(
          x,
          y,
          segmentWidth,
          7,
          'F',
        )
      }

      y += rowHeight
    }

    if (overlaps.length) {
      doc.setFontSize(8)
      doc.setFont(
        'helvetica',
        'bold',
      )

      doc.setTextColor(
        185,
        28,
        28,
      )

      doc.text(
        'OVERLAP',
        14,
        y + 5,
      )

      doc.setFillColor(
        254,
        226,
        226,
      )

      doc.rect(
        left,
        y,
        width,
        7,
        'F',
      )

      for (
        const overlap of overlaps
      ) {
        const start =
          safeNumber(
            overlap.start,
          )

        const end =
          safeNumber(
            overlap.end,
          )

        const x =
          left +
          (start / duration) *
            width

        const overlapWidth =
          Math.max(
            0.5,
            (
              (end - start) /
              duration
            ) * width,
          )

        doc.setFillColor(
          220,
          38,
          38,
        )

        doc.rect(
          x,
          y,
          overlapWidth,
          7,
          'F',
        )
      }

      y += rowHeight
    }

    doc.setFontSize(7)
    doc.setFont(
      'helvetica',
      'normal',
    )

    doc.setTextColor(
      100,
      116,
      139,
    )

    const ticks = 5

    for (
      let index = 0;
      index <= ticks;
      index++
    ) {
      const fraction =
        index / ticks

      const x =
        left +
        fraction * width

      doc.text(
        formatSeconds(
          duration * fraction,
        ),
        x,
        y + 3,
        {
          align:
            index === 0
              ? 'left'
              : index === ticks
                ? 'right'
                : 'center',
        },
      )
    }

    return y + 10
  }

  async function createWaveformImage(file) {
    if (!file) {
      return null
    }

    const arrayBuffer =
      await file.arrayBuffer()

    const AudioContextClass =
      window.AudioContext ||
      window.webkitAudioContext

    const audioContext =
      new AudioContextClass()

    try {
      const audioBuffer =
        await audioContext.decodeAudioData(
          arrayBuffer.slice(0)
        )

      const channel =
        audioBuffer.getChannelData(0)

      const width = 1600
      const height = 320

      const canvas =
        document.createElement('canvas')

      canvas.width = width
      canvas.height = height

      const ctx =
        canvas.getContext('2d')

      ctx.fillStyle = '#ffffff'

      ctx.fillRect(
        0,
        0,
        width,
        height,
      )

      // Horizontal centre line.
      ctx.strokeStyle = '#cbd5e1'
      ctx.lineWidth = 1

      ctx.beginPath()

      ctx.moveTo(
        0,
        height / 2,
      )

      ctx.lineTo(
        width,
        height / 2,
      )

      ctx.stroke()

      // Light vertical grid.
      ctx.strokeStyle = '#e2e8f0'

      for (
        let i = 0;
        i <= 10;
        i++
      ) {
        const x =
          (i / 10) * width

        ctx.beginPath()

        ctx.moveTo(
          x,
          0,
        )

        ctx.lineTo(
          x,
          height,
        )

        ctx.stroke()
      }

      const samplesPerPixel =
        Math.max(
          1,
          Math.floor(
            channel.length / width
          ),
        )

      ctx.strokeStyle = '#475569'
      ctx.lineWidth = 1

      for (
        let x = 0;
        x < width;
        x++
      ) {
        const start =
          x * samplesPerPixel

        const end =
          Math.min(
            start + samplesPerPixel,
            channel.length,
          )

        let min = 1
        let max = -1

        for (
          let index = start;
          index < end;
          index++
        ) {
          const value =
            channel[index]

          if (value < min) {
            min = value
          }

          if (value > max) {
            max = value
          }
        }

        const yTop =
          ((1 - max) / 2) *
          height

        const yBottom =
          ((1 - min) / 2) *
          height

        ctx.beginPath()

        ctx.moveTo(
          x,
          yTop,
        )

        ctx.lineTo(
          x,
          yBottom,
        )

        ctx.stroke()
      }

      return canvas.toDataURL(
        'image/png'
      )
    } finally {
      await audioContext.close()
    }
  }

  function mergeIntervals(intervals) {
    if (!intervals.length) {
      return []
    }

    const ordered = intervals
      .map(([start, end]) => [
        safeNumber(start),
        safeNumber(end),
      ])
      .filter(
        ([start, end]) =>
          end > start
      )
      .sort(
        (a, b) =>
          a[0] - b[0]
      )

    if (!ordered.length) {
      return []
    }

    const merged = [
      [...ordered[0]],
    ]

    for (
      let index = 1;
      index < ordered.length;
      index++
    ) {
      const current =
        ordered[index]

      const previous =
        merged[
          merged.length - 1
        ]

      if (
        current[0] <=
        previous[1]
      ) {
        previous[1] =
          Math.max(
            previous[1],
            current[1],
          )
      } else {
        merged.push(
          [...current]
        )
      }
    }

    return merged
  }


  function buildAnalysisSummary(
    result
  ) {
    const speakers =
      result.speakers || []

    const segments =
      result.segments || []

    const overlaps =
      result.overlaps || []

    const stats =
      result.speaker_stats || {}

    const duration =
      Math.max(
        0,
        safeNumber(
          result.audio_duration_seconds
        ),
      )

    const rankedSpeakers =
      speakers
        .map(
          speaker => {
            const speakerStats =
              stats[speaker] || {}

            return {
              speaker,

              speakingSeconds:
                safeNumber(
                  speakerStats
                    .speaking_seconds
                ),

              percentage:
                safeNumber(
                  speakerStats
                    .speaking_percentage
                ),

              segmentCount:
                safeNumber(
                  speakerStats
                    .segment_count
                ),
            }
          }
        )
        .sort(
          (a, b) =>
            b.speakingSeconds -
            a.speakingSeconds
        )

    const segmentDurations =
      segments
        .map(
          segment => ({
            speaker:
              segment.speaker,

            start:
              safeNumber(
                segment.start
              ),

            end:
              safeNumber(
                segment.end
              ),

            duration:
              Math.max(
                0,
                safeNumber(
                  segment.end
                ) -
                safeNumber(
                  segment.start
                ),
              ),
          })
        )
        .filter(
          segment =>
            segment.duration > 0
        )

    const longestSegment =
      segmentDurations
        .reduce(
          (
            longest,
            segment,
          ) =>
            !longest ||
            segment.duration >
              longest.duration
              ? segment
              : longest,
          null,
        )

    const averageSegmentSeconds =
      segmentDurations.length
        ? segmentDurations
            .reduce(
              (
                total,
                segment,
              ) =>
                total +
                segment.duration,
              0,
            ) /
          segmentDurations.length
        : 0

    /*
    * Use the union of all diarization
    * intervals rather than summing
    * speaker durations.
    *
    * This avoids double-counting
    * overlapping speech.
    */
    const mergedSpeech =
      mergeIntervals(
        segments.map(
          segment => [
            segment.start,
            segment.end,
          ]
        )
      )

    const detectedSpeechSeconds =
      mergedSpeech.reduce(
        (
          total,
          [start, end],
        ) =>
          total +
          Math.max(
            0,
            end - start
          ),
        0,
      )

    const speechCoverage =
      duration > 0
        ? Math.min(
            100,
            (
              detectedSpeechSeconds /
              duration
            ) * 100,
          )
        : 0

    const overlapSeconds =
      safeNumber(
        result.overlap_seconds
      )

    const overlapPercentage =
      duration > 0
        ? Math.min(
            100,
            (
              overlapSeconds /
              duration
            ) * 100,
          )
        : 0

    return {
      duration,
      rankedSpeakers,
      longestSegment,
      averageSegmentSeconds,
      detectedSpeechSeconds,
      speechCoverage,

      overlapCount:
        safeNumber(
          result.overlap_count
        ),

      overlapSeconds,
      overlapPercentage,

      inferenceSeconds:
        safeNumber(
          result.inference_seconds
        ),

      realTimeFactor:
        safeNumber(
          result.real_time_factor
        ),

      device:
        String(
          result.device ||
          'unknown'
        ).toUpperCase(),
    }
  }

  function buildInterpretationSections(
    result
  ) {
    const analysis =
      buildAnalysisSummary(
        result
      )

    const dominant =
      analysis.rankedSpeakers[0]

    const sections = []

    sections.push({
      title:
        'Recording overview',

      text:
        `The recording produced ` +
        `${safeNumber(
          result.speaker_count
        )} distinct speaker cluster` +
        `${
          safeNumber(
            result.speaker_count
          ) === 1
            ? ''
            : 's'
        } across ` +
        `${safeNumber(
          result.segment_count
        )} detected speech segment` +
        `${
          safeNumber(
            result.segment_count
          ) === 1
            ? ''
            : 's'
        }. ` +
        `The analyzed recording duration ` +
        `was approximately ` +
        `${analysis.duration.toFixed(2)} ` +
        `seconds.`,
    })

    if (dominant) {
      let participation =
        `${dominant.speaker} was the ` +
        `dominant detected speaker, ` +
        `with approximately ` +
        `${dominant.speakingSeconds
          .toFixed(2)} seconds of ` +
        `speaker activity ` +
        `(${dominant.percentage
          .toFixed(1)}%) across ` +
        `${dominant.segmentCount} ` +
        `segment` +
        `${
          dominant.segmentCount === 1
            ? ''
            : 's'
        }.`

      if (
        analysis.rankedSpeakers
          .length > 1
      ) {
        const others =
          analysis.rankedSpeakers
            .slice(1)
            .map(
              speaker =>
                `${speaker.speaker}: ` +
                `${speaker
                  .speakingSeconds
                  .toFixed(2)} s ` +
                `(${speaker
                  .percentage
                  .toFixed(1)}%, ` +
                `${speaker
                  .segmentCount} ` +
                `segment${
                  speaker
                    .segmentCount === 1
                    ? ''
                    : 's'
                })`
            )
            .join('; ')

        participation +=
          ` Other detected speaker ` +
          `activity was: ${others}.`
      }

      sections.push({
        title:
          'Speaker participation',

        text:
          participation,
      })
    }

    if (
      analysis.longestSegment
    ) {
      sections.push({
        title:
          'Turn structure',

        text:
          `The longest continuous ` +
          `detected speaker segment ` +
          `lasted approximately ` +
          `${analysis.longestSegment
            .duration
            .toFixed(2)} seconds and ` +
          `was assigned to ` +
          `${analysis.longestSegment
            .speaker}. ` +
          `Across all detected segments, ` +
          `the average segment duration ` +
          `was approximately ` +
          `${analysis
            .averageSegmentSeconds
            .toFixed(2)} seconds.`,
      })
    }

    if (
      analysis.overlapCount > 0
    ) {
      sections.push({
        title:
          'Cross-talk analysis',

        text:
          `${analysis.overlapCount} ` +
          `overlapping-speech interval` +
          `${
            analysis.overlapCount === 1
              ? ' was'
              : 's were'
          } detected, totalling ` +
          `approximately ` +
          `${analysis.overlapSeconds
            .toFixed(2)} seconds. ` +
          `This represents approximately ` +
          `${analysis.overlapPercentage
            .toFixed(1)}% of the ` +
          `recording duration. ` +
          `These regions indicate periods ` +
          `where activity from more than ` +
          `one speaker cluster overlaps ` +
          `in time.`,
      })
    } else {
      sections.push({
        title:
          'Cross-talk analysis',

        text:
          `No overlapping-speech ` +
          `intervals were detected in ` +
          `this recording. The diarization ` +
          `output therefore contains no ` +
          `identified periods of ` +
          `simultaneous activity between ` +
          `different speaker clusters.`,
      })
    }

    const remaining =
      Math.max(
        0,
        analysis.duration -
        analysis.detectedSpeechSeconds
      )

    sections.push({
      title:
        'Detected speech coverage',

      text:
        `Diarized speech intervals cover ` +
        `approximately ` +
        `${analysis.speechCoverage
          .toFixed(1)}% of the analyzed ` +
        `recording ` +
        `(${analysis.detectedSpeechSeconds
          .toFixed(2)} seconds). ` +
        `Approximately ` +
        `${remaining.toFixed(2)} seconds ` +
        `fall outside detected speaker ` +
        `intervals and may contain silence, ` +
        `background sound, non-speech ` +
        `content, or regions not assigned ` +
        `to a speaker cluster.`,
    })

    sections.push({
      title:
        'Processing performance',

      text:
        `Inference completed on ` +
        `${analysis.device} in ` +
        `${analysis.inferenceSeconds
          .toFixed(2)} seconds, with a ` +
        `real-time factor of ` +
        `${analysis.realTimeFactor
          .toFixed(2)}x. ` +
        (
          analysis.realTimeFactor > 0 &&
          analysis.realTimeFactor < 1
            ? `For this recording, the ` +
              `model completed inference ` +
              `faster than the duration ` +
              `of the input audio.`
            : analysis.realTimeFactor >= 1
              ? `For this recording, ` +
                `inference required at ` +
                `least as much processing ` +
                `time as the input audio ` +
                `duration.`
              : ''
        ),
    })

    sections.push({
      title:
        'Interpretation limits',

      text:
        `Speaker labels such as ` +
        `SPEAKER_00 are anonymous ` +
        `model-generated cluster ` +
        `identifiers. They do not ` +
        `establish the real-world ` +
        `identity of a speaker. ` +
        `Speaker boundaries, overlap ` +
        `regions, participation measures, ` +
        `and timing statistics are ` +
        `automated estimates and may be ` +
        `affected by recording quality, ` +
        `noise, reverberation, short ` +
        `utterances, cross-talk, and ` +
        `domain mismatch. This report is ` +
        `intended for analysis and ` +
        `demonstration use and is not a ` +
        `forensic identity determination ` +
        `or expert legal opinion.`,
    })

    return sections
  }

  function drawInterpretationSections(
    doc,
    sections,
    startY = 38,
  ) {
    let y =
      startY

    const pageBottom =
      270

    const textWidth =
      176

    for (
      const section of sections
    ) {
      const lines =
        doc.splitTextToSize(
          section.text,
          textWidth,
        )

      const estimatedHeight =
        8 +
        lines.length * 5

      if (
        y +
        estimatedHeight >
        pageBottom
      ) {
        doc.addPage()

        addPageHeader(
          doc,
          'Automated interpretation — continued',
        )

        y = 38
      }

      doc.setFont(
        'helvetica',
        'bold',
      )

      doc.setFontSize(11)

      doc.setTextColor(
        15,
        23,
        42,
      )

      doc.text(
        section.title,
        14,
        y,
      )

      y += 7

      doc.setFont(
        'helvetica',
        'normal',
      )

      doc.setFontSize(9.5)

      doc.setTextColor(
        51,
        65,
        85,
      )

      doc.text(
        lines,
        14,
        y,
        {
          lineHeightFactor: 1.45,
        },
      )

      y +=
        lines.length * 5 +
        9
    }
  }
  
  async function generateDiarizationReport(
    result,
    file,
  ) {
    if (
      !window.jspdf ||
      !window.jspdf.jsPDF
    ) {
      throw new Error(
        'jsPDF is not available.',
      )
    }

    if (!result) {
      throw new Error(
        'No diarization result is available.',
      )
    }

    const {
      jsPDF,
    } = window.jspdf

    const doc =
      new jsPDF({
        unit: 'mm',
        format: 'a4',
        orientation: 'portrait',
      })

    const filename =
      file?.name ||
      result.filename ||
      'audio'

    addPageHeader(
      doc,
      'Analysis summary',
    )

    doc.setFontSize(9)
    doc.setFont(
      'helvetica',
      'normal',
    )
    doc.setTextColor(
      51,
      65,
      85,
    )

    doc.text(
      `File: ${filename}`,
      14,
      36,
    )

    doc.text(
      `Generated: ${new Date().toLocaleString()}`,
      14,
      42,
    )

    const metricWidth = 56

    drawMetric(
      doc,
      14,
      50,
      metricWidth,
      'Speakers',
      result.speaker_count,
    )

    drawMetric(
      doc,
      76,
      50,
      metricWidth,
      'Segments',
      result.segment_count,
    )

    drawMetric(
      doc,
      138,
      50,
      metricWidth,
      'Duration',
      formatSeconds(
        result.audio_duration_seconds,
      ),
    )

    drawMetric(
      doc,
      14,
      76,
      metricWidth,
      'Inference',
      `${safeNumber(
        result.inference_seconds,
      ).toFixed(2)} s`,
    )

    drawMetric(
      doc,
      76,
      76,
      metricWidth,
      'Real-time factor',
      `${safeNumber(
        result.real_time_factor,
      ).toFixed(2)}x`,
    )

    drawMetric(
      doc,
      138,
      76,
      metricWidth,
      'Device',
      String(
        result.device || 'unknown',
      ).toUpperCase(),
    )

    doc.setFontSize(11)
    doc.setFont(
      'helvetica',
      'bold',
    )

    doc.setTextColor(
      15,
      23,
      42,
    )

    doc.text(
      'Speaker statistics',
      14,
      108,
    )

    const speakerRows =
      (result.speakers || [])
        .map(
          speaker => {
            const stats =
              result
                .speaker_stats?.[
                  speaker
                ] || {}

            return [
              speaker,
              safeNumber(
                stats.segment_count,
              ),
              `${safeNumber(
                stats.speaking_seconds,
              ).toFixed(2)} s`,
              `${safeNumber(
                stats.speaking_percentage,
              ).toFixed(1)}%`,
            ]
          },
        )

    doc.autoTable({
      startY: 113,
      head: [[
        'Speaker',
        'Segments',
        'Speaking',
        'Share',
      ]],
      body: speakerRows,
      theme: 'grid',
      styles: {
        fontSize: 8,
        cellPadding: 2.5,
      },
      headStyles: {
        fillColor: [
          30,
          41,
          59,
        ],
      },
      margin: {
        left: 14,
        right: 14,
      },
    })
    doc.setFontSize(7.5)

    doc.setFont(
      'helvetica',
      'italic',
    )

    doc.setTextColor(
      100,
      116,
      139,
    )

    const speakerShareNote =
      doc.splitTextToSize(
        'Speaker shares are measured independently against total recording duration and may sum above 100% when overlapping speech is present.',
        180,
      )

    doc.text(
      speakerShareNote,
      14,
      (doc.lastAutoTable?.finalY || 130) + 6,
    )

    // ==========================================
    // PAGE 2: VISUAL SPEAKER ANALYSIS
    // ==========================================

    doc.addPage()

    addPageHeader(
      doc,
      'Visual speaker analysis',
    )

    const waveformImage =
      await createWaveformImage(file)

    doc.setFontSize(11)

    doc.setFont(
      'helvetica',
      'bold',
    )

    doc.setTextColor(
      15,
      23,
      42,
    )

    doc.text(
      'Audio amplitude waveform',
      14,
      38,
    )

    if (waveformImage) {
      doc.addImage(
        waveformImage,
        'PNG',
        14,
        44,
        180,
        50,
      )
    }

    const timelineEndY =
      drawSpeakerTimeline(
        doc,
        result,
        112,
      )

    doc.setFontSize(9)

    doc.setFont(
      'helvetica',
      'normal',
    )

    doc.setTextColor(
      51,
      65,
      85,
    )

    doc.text(
      `Overlap: ${
        safeNumber(
          result.overlap_count,
        )
      } interval(s), ${
        safeNumber(
          result.overlap_seconds,
        ).toFixed(2)
      } s total`,
      14,
      timelineEndY,
    )

    doc.addPage()

    addPageHeader(
      doc,
      'Speaker segment log',
    )

    const segmentRows =
      (result.segments || [])
        .map(
          (
            segment,
            index,
          ) => [
            index + 1,
            segment.speaker,
            formatSeconds(
              segment.start,
            ),
            formatSeconds(
              segment.end,
            ),
            `${Math.max(
              0,
              safeNumber(
                segment.end,
              ) -
              safeNumber(
                segment.start,
              ),
            ).toFixed(2)} s`,
          ],
        )

    doc.autoTable({
      startY: 34,
      head: [[
        '#',
        'Speaker',
        'Start',
        'End',
        'Duration',
      ]],
      body: segmentRows,
      theme: 'striped',
      styles: {
        fontSize: 8,
        cellPadding: 2.2,
      },
      headStyles: {
        fillColor: [
          30,
          41,
          59,
        ],
      },
      margin: {
        left: 14,
        right: 14,
        bottom: 18,
      },
      didDrawPage: data => {
        if (
          data.pageNumber > 1
        ) {
          addPageHeader(
            doc,
            'Speaker segment log — continued',
          )
        }
      },
    })

    if (
      (result.overlaps || [])
        .length
    ) {
      doc.addPage()

      addPageHeader(
        doc,
        'Overlapping speech',
      )

      const overlapRows =
        result.overlaps.map(
          (
            overlap,
            index,
          ) => [
            index + 1,
            formatSeconds(
              overlap.start,
            ),
            formatSeconds(
              overlap.end,
            ),
            `${Math.max(
              0,
              safeNumber(
                overlap.end,
              ) -
              safeNumber(
                overlap.start,
              ),
            ).toFixed(2)} s`,
          ],
        )

      doc.autoTable({
        startY: 34,
        head: [[
          '#',
          'Start',
          'End',
          'Duration',
        ]],
        body: overlapRows,
        theme: 'striped',
        styles: {
          fontSize: 8,
          cellPadding: 2.4,
        },
        headStyles: {
          fillColor: [
            185,
            28,
            28,
          ],
        },
        margin: {
          left: 14,
          right: 14,
        },
      })
    }

    // ==========================================
    // FINAL PAGE: AUTOMATED INTERPRETATION
    // ==========================================

    doc.addPage()

    addPageHeader(
      doc,
      'Automated interpretation',
    )

    const interpretationSections =
      buildInterpretationSections(
        result
      )

    drawInterpretationSections(
      doc,
      interpretationSections,
      38,
    )
    
    addFooter(doc)

    return doc
  }

  function reportFilename(file) {
    return (
      `${baseFilename(
        file?.name,
      )}-diarization-report.pdf`
    )
  }

  window.DiarizationReport = {
    async generate(
      result,
      file,
    ) {
      return await generateDiarizationReport(
        result,
        file,
      )
    },

    async createBlob(
      result,
      file,
    ) {
      const doc =
        await generateDiarizationReport(
          result,
          file,
        )

      return doc.output('blob')
    },

    async download(
      result,
      file,
    ) {
      const doc =
        await generateDiarizationReport(
          result,
          file,
        )

      doc.save(
        reportFilename(file),
      )
    },

    filename:
      reportFilename,
  }
})()
