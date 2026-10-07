// turn-ding: rings a sound while every other app's audio is turned down.
//
// usage: turn-ding <sound file> <repeat> <ring seconds> <duck gain 0..1>
//
// The turning down is the system mixer's own (AudioDeviceDuck, the call
// behind voice-chat ducking): the other apps' streams are untouched and only
// scaled, so the slide is smooth. The call is exported by CoreAudio but is in
// no public header; when it fails this exits 1 without ringing, and the
// caller rings some other way.

import AVFoundation
import CoreAudio
import Foundation

@_silgen_name("AudioDeviceDuck")
func AudioDeviceDuck(_ device: AudioDeviceID, _ level: Float32,
                     _ startTime: UnsafePointer<AudioTimeStamp>?, _ rampSeconds: Float32) -> OSStatus

// How long the other apps take to slide down, and back up
let rampSeconds: Float32 = 0.5

func fail(_ text: String, code: Int32 = 1) -> Never {
    FileHandle.standardError.write("turn-ding: \(text)\n".data(using: .utf8)!)
    exit(code)
}

let args = CommandLine.arguments
guard args.count == 5, let repeatCount = Int(args[2]), let ringSeconds = Double(args[3]),
      let duckGain = Float(args[4]) else {
    fail("usage: turn-ding <sound file> <repeat> <ring seconds> <duck gain>", code: 2)
}

var device = AudioObjectID(kAudioObjectUnknown)
var size = UInt32(MemoryLayout<AudioObjectID>.size)
var defaultOutput = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
                                               mScope: kAudioObjectPropertyScopeGlobal,
                                               mElement: kAudioObjectPropertyElementMain)
guard AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &defaultOutput, 0, nil,
                                 &size, &device) == noErr else {
    fail("no output device")
}
guard let player = try? AVAudioPlayer(contentsOf: URL(fileURLWithPath: args[1])) else {
    fail("cannot play \(args[1])")
}
player.prepareToPlay()

// A kill while ducked still hands the other apps their level back
let outputDevice = device
for signalNumber in [SIGINT, SIGTERM, SIGHUP] {
    signal(signalNumber, SIG_IGN)
    let source = DispatchSource.makeSignalSource(signal: signalNumber, queue: .global())
    source.setEventHandler {
        _ = AudioDeviceDuck(outputDevice, 1, nil, 0)
        exit(1)
    }
    source.resume()
}

let status = AudioDeviceDuck(device, duckGain, nil, rampSeconds)
guard status == noErr else { fail("AudioDeviceDuck failed (\(status))") }
Thread.sleep(forTimeInterval: Double(rampSeconds) + 0.1)

for _ in 0..<repeatCount {
    player.currentTime = 0
    player.play()
    Thread.sleep(forTimeInterval: ringSeconds)
    player.stop()
}

_ = AudioDeviceDuck(device, 1, nil, rampSeconds)
Thread.sleep(forTimeInterval: Double(rampSeconds) + 0.1)
