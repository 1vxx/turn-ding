// turn-ding: rings a sound while every other app's audio is turned down.
//
// usage: turn-ding <sound file> <repeat> <ring seconds> <duck gain 0..1>
//        turn-ding state
//
// `state` rings nothing: it prints where the person is, as
// "<seconds since their last key or pointer input> <1 when the screen is
// locked> <1 when the app this session runs in is the frontmost one>".
//
// The turning down is the system mixer's own (AudioDeviceDuck, the call
// behind voice-chat ducking): the other apps' streams are untouched and only
// scaled, so the slide is smooth. The call is exported by CoreAudio but is in
// no public header; when it fails this exits 1 without ringing, and the
// caller rings some other way.

import AVFoundation
import AppKit
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

// Terminals whose shells are not their own descendants (a server process, a
// multiplexer in between), so the walk up from this process never meets them
let terminals: Set<String> = ["com.apple.Terminal", "com.googlecode.iterm2", "dev.warp.Warp-Stable",
                              "com.mitchellh.ghostty", "net.kovidgoyal.kitty", "org.alacritty",
                              "com.github.wez.wezterm"]

func parent(of pid: pid_t) -> pid_t? {
    var info = kinfo_proc()
    var size = MemoryLayout<kinfo_proc>.stride
    var name = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
    guard sysctl(&name, 4, &info, &size, nil, 0) == 0, size > 0 else { return nil }
    return info.kp_eproc.e_ppid
}

// The session's app is in front when the frontmost app is an ancestor of this
// process (the desktop app, an editor's terminal), or one of the terminals
func isHostFrontmost() -> Bool {
    guard let front = NSWorkspace.shared.frontmostApplication else { return false }
    var pid = getpid()
    while pid > 1, let up = parent(of: pid) {
        if up == front.processIdentifier { return true }
        pid = up
    }
    return terminals.contains(front.bundleIdentifier ?? "")
}

let args = CommandLine.arguments
if args.count == 2, args[1] == "state" {
    let idle = CGEventSource.secondsSinceLastEventType(.combinedSessionState,
                                                       eventType: CGEventType(rawValue: ~0)!)
    let session = CGSessionCopyCurrentDictionary() as? [String: Any]
    let isLocked = session?["CGSSessionScreenIsLocked"] as? Bool ?? false
    print("\(Int(idle)) \(isLocked ? 1 : 0) \(isHostFrontmost() ? 1 : 0)")
    exit(0)
}
guard args.count == 5, let repeatCount = Int(args[2]), let ringSeconds = Double(args[3]),
      let duckGain = Float(args[4]) else {
    fail("usage: turn-ding <sound file> <repeat> <ring seconds> <duck gain> | turn-ding state", code: 2)
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

// A gain of 1 leaves the other apps alone, so there is nothing to wait for
let isDucking = duckGain < 1
if isDucking {
    let status = AudioDeviceDuck(device, duckGain, nil, rampSeconds)
    guard status == noErr else { fail("AudioDeviceDuck failed (\(status))") }
    Thread.sleep(forTimeInterval: Double(rampSeconds) + 0.1)
}

for _ in 0..<repeatCount {
    player.currentTime = 0
    player.play()
    Thread.sleep(forTimeInterval: ringSeconds)
    player.stop()
}

if isDucking {
    _ = AudioDeviceDuck(device, 1, nil, rampSeconds)
    Thread.sleep(forTimeInterval: Double(rampSeconds) + 0.1)
}
