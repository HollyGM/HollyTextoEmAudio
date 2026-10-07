import Cocoa

// Ícone vetorial, gerado em todas as resoluções exigidas pelo iconutil.
func renderIcon(pixels: Int, to destination: URL) throws {
    guard let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
                                        bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                        isPlanar: false, colorSpaceName: .deviceRGB,
                                        bytesPerRow: 0, bitsPerPixel: 0),
          let context = NSGraphicsContext(bitmapImageRep: bitmap) else {
        throw NSError(domain: "TextoAudioIcone", code: 1)
    }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    let transform = NSAffineTransform()
    transform.scale(by: CGFloat(pixels) / 1024)
    transform.concat()

    let background = NSBezierPath(roundedRect: NSRect(x: 48, y: 48, width: 928, height: 928),
                                  xRadius: 205, yRadius: 205)
    let blue = NSColor(srgbRed: 0.15, green: 0.42, blue: 0.88, alpha: 1)
    let darkBlue = NSColor(srgbRed: 0.05, green: 0.19, blue: 0.49, alpha: 1)
    NSGradient(starting: darkBlue, ending: blue)?.draw(in: background, angle: 65)

    NSGraphicsContext.saveGraphicsState()
    let shadow = NSShadow()
    shadow.shadowColor = NSColor.black.withAlphaComponent(0.18)
    shadow.shadowBlurRadius = 28
    shadow.shadowOffset = NSSize(width: 0, height: -16)
    shadow.set()
    NSColor.white.setFill()
    NSBezierPath(roundedRect: NSRect(x: 218, y: 216, width: 444, height: 606),
                 xRadius: 40, yRadius: 40).fill()
    NSGraphicsContext.restoreGraphicsState()

    let fold = NSBezierPath()
    fold.move(to: NSPoint(x: 552, y: 822))
    fold.line(to: NSPoint(x: 662, y: 712))
    fold.line(to: NSPoint(x: 571, y: 712))
    fold.curve(to: NSPoint(x: 552, y: 731), controlPoint1: NSPoint(x: 559, y: 712),
               controlPoint2: NSPoint(x: 552, y: 719))
    fold.close()
    NSColor(srgbRed: 0.76, green: 0.87, blue: 1, alpha: 1).setFill()
    fold.fill()

    NSColor(srgbRed: 0.18, green: 0.39, blue: 0.67, alpha: 1).setStroke()
    for (y, end) in [(662.0, 538.0), (579.0, 554.0), (496.0, 474.0)] {
        let line = NSBezierPath()
        line.lineWidth = 30
        line.lineCapStyle = .round
        line.move(to: NSPoint(x: 292, y: y))
        line.line(to: NSPoint(x: end, y: y))
        line.stroke()
    }

    NSGraphicsContext.saveGraphicsState()
    shadow.set()
    NSColor(srgbRed: 0.04, green: 0.19, blue: 0.45, alpha: 1).setFill()
    NSBezierPath(ovalIn: NSRect(x: 470, y: 140, width: 405, height: 405)).fill()
    NSGraphicsContext.restoreGraphicsState()

    NSColor(srgbRed: 0.39, green: 0.88, blue: 0.97, alpha: 1).setStroke()
    for (index, height) in [62.0, 125.0, 212.0, 143.0, 78.0].enumerated() {
        let line = NSBezierPath()
        line.lineCapStyle = .round
        line.lineWidth = 31
        let x = 564 + Double(index) * 54
        line.move(to: NSPoint(x: x, y: 343 - height / 2))
        line.line(to: NSPoint(x: x, y: 343 + height / 2))
        line.stroke()
    }
    NSGraphicsContext.restoreGraphicsState()
    guard let png = bitmap.representation(using: .png, properties: [:]) else {
        throw NSError(domain: "TextoAudioIcone", code: 2)
    }
    try png.write(to: destination, options: .atomic)
}

do {
    guard CommandLine.arguments.count == 2 else {
        throw NSError(domain: "TextoAudioIcone", code: 3,
                      userInfo: [NSLocalizedDescriptionKey: "Uso: icone caminho/AppIcon.iconset"])
    }
    let directory = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    for size in [16, 32, 128, 256, 512] {
        try renderIcon(pixels: size, to: directory.appendingPathComponent("icon_\(size)x\(size).png"))
        try renderIcon(pixels: size * 2, to: directory.appendingPathComponent("icon_\(size)x\(size)@2x.png"))
    }
} catch {
    FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
    exit(1)
}
