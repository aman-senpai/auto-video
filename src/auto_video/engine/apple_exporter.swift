import AVFoundation
import Foundation

enum ExporterError: Error, LocalizedError {
    case usage
    case missingVideoTrack
    case exportSessionUnavailable
    case unsupportedPreset
    case exportFailed(String)

    var errorDescription: String? {
        switch self {
        case .usage:
            return "Usage: apple_exporter <video> <audio> <output>"
        case .missingVideoTrack:
            return "Video file does not contain a video track."
        case .exportSessionUnavailable:
            return "Unable to create AVAssetExportSession."
        case .unsupportedPreset:
            return "No supported Apple export preset found for this asset."
        case let .exportFailed(message):
            return message
        }
    }
}

func emit(_ payload: [String: String]) {
    guard let data = try? JSONSerialization.data(withJSONObject: payload, options: []),
          let line = String(data: data, encoding: .utf8) else {
        return
    }
    FileHandle.standardOutput.write(Data((line + "\n").utf8))
}

func preferredPreset(for asset: AVComposition) -> String? {
    let candidates = [
        AVAssetExportPresetHEVCHighestQuality,
        AVAssetExportPresetHighestQuality,
        AVAssetExportPreset1920x1080,
    ]
    let supported = AVAssetExportSession.exportPresets(compatibleWith: asset)
    return candidates.first(where: { supported.contains($0) })
}

@main
struct AppleExporter {
    static func main() async throws {
        let args = CommandLine.arguments
        guard args.count == 4 else {
            throw ExporterError.usage
        }

        let videoURL = URL(fileURLWithPath: args[1])
        let audioURL = URL(fileURLWithPath: args[2])
        let outputURL = URL(fileURLWithPath: args[3])

        let videoAsset = AVURLAsset(url: videoURL)
        let audioAsset = AVURLAsset(url: audioURL)
        let composition = AVMutableComposition()

        guard let videoTrack = try await videoAsset.loadTracks(withMediaType: .video).first else {
            throw ExporterError.missingVideoTrack
        }

        let audioTrack = try await audioAsset.loadTracks(withMediaType: .audio).first
        let videoDuration = try await videoAsset.load(.duration)
        let audioDuration = try await audioAsset.load(.duration)

        let compositionVideoTrack = composition.addMutableTrack(withMediaType: .video, preferredTrackID: kCMPersistentTrackID_Invalid)
        try compositionVideoTrack?.insertTimeRange(CMTimeRange(start: .zero, duration: videoDuration), of: videoTrack, at: .zero)
        compositionVideoTrack?.preferredTransform = try await videoTrack.load(.preferredTransform)

        if let audioTrack, let compositionAudioTrack = composition.addMutableTrack(withMediaType: .audio, preferredTrackID: kCMPersistentTrackID_Invalid) {
            let shorterDuration = CMTimeMinimum(videoDuration, audioDuration)
            try compositionAudioTrack.insertTimeRange(CMTimeRange(start: .zero, duration: shorterDuration), of: audioTrack, at: .zero)
        }

        guard let preset = preferredPreset(for: composition) else {
            throw ExporterError.unsupportedPreset
        }
        guard let exportSession = AVAssetExportSession(asset: composition, presetName: preset) else {
            throw ExporterError.exportSessionUnavailable
        }

        try? FileManager.default.removeItem(at: outputURL)
        exportSession.outputURL = outputURL
        exportSession.outputFileType = .mp4
        exportSession.shouldOptimizeForNetworkUse = true
        exportSession.timeRange = CMTimeRange(start: .zero, duration: CMTimeMinimum(videoDuration, audioDuration))

        emit(["event": "started", "preset": preset])

        let timer = DispatchSource.makeTimerSource(queue: DispatchQueue.global(qos: .utility))
        timer.schedule(deadline: .now(), repeating: .milliseconds(200))
        timer.setEventHandler {
            let progress = String(format: "%.3f", exportSession.progress)
            emit(["event": "progress", "value": progress])
        }
        timer.resume()

        await exportSession.export()
        timer.cancel()

        switch exportSession.status {
        case .completed:
            emit(["event": "completed", "output": outputURL.path])
        case .failed:
            throw ExporterError.exportFailed(exportSession.error?.localizedDescription ?? "Native export failed.")
        case .cancelled:
            throw ExporterError.exportFailed("Native export cancelled.")
        default:
            throw ExporterError.exportFailed("Native export ended in unexpected state: \(exportSession.status.rawValue)")
        }
    }
}
