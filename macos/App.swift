import Cocoa
import WebKit
import UniformTypeIdentifiers

/// A interface e o servidor permanecem locais. O texto do usuário não passa pelo launcher.
@MainActor
final class TextoAudioApp: NSObject, NSApplicationDelegate, NSWindowDelegate,
    WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate, WKScriptMessageHandler {

    private var window: NSWindow!
    private var webView: WKWebView!
    private var backend: Process?
    private var logHandle: FileHandle?
    private var readinessTimer: Timer?
    private var readinessDeadline = Date()
    private var stateDirectory: URL?
    private var stateFile: URL?
    private var serverURL: URL?
    private var failed = false
    private var shuttingDown = false
    private var checkingTermination = false
    private var downloads: [ObjectIdentifier: WKDownload] = [:]
    private var destinations: [ObjectIdentifier: URL] = [:]
    private var downloadStagingFiles: [ObjectIdentifier: URL] = [:]
    private var cancelledDownloads: Set<ObjectIdentifier> = []

    private let dataDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/Texto em Áudio", isDirectory: true)
    private let outputDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Music/Texto em Áudio", isDirectory: true)
    private let logDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Logs/Texto em Áudio", isDirectory: true)
    private var logFile: URL { logDirectory.appendingPathComponent("aplicativo.log") }
    private var preferencesFile: URL { dataDirectory.appendingPathComponent("preferencias.json") }

    func applicationDidFinishLaunching(_ notification: Notification) {
        createMenu()
        createWindow()
        launchBackend()
    }

    private func createMenu() {
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = NSMenu(title: "Texto em Áudio")
        appMenu.addItem(withTitle: "Sobre Texto em Áudio", action: #selector(showAbout), keyEquivalent: "")
            .target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Ocultar Texto em Áudio", action: #selector(NSApplication.hide(_:)),
                        keyEquivalent: "h")
        let hideOthers = appMenu.addItem(withTitle: "Ocultar Outros", action: #selector(NSApplication.hideOtherApplications(_:)),
                                        keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        appMenu.addItem(withTitle: "Mostrar Todos", action: #selector(NSApplication.unhideAllApplications(_:)),
                        keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Sair de Texto em Áudio", action: #selector(NSApplication.terminate(_:)),
                        keyEquivalent: "q")
        appItem.submenu = appMenu
        menu.addItem(appItem)

        let fileItem = NSMenuItem()
        let fileMenu = NSMenu(title: "Arquivo")
        fileMenu.addItem(withTitle: "Abrir Pasta dos MP3", action: #selector(openOutputDirectory),
                         keyEquivalent: "o").target = self
        fileMenu.addItem(withTitle: "Editar Pronúncias", action: #selector(openPronunciations),
                         keyEquivalent: "").target = self
        fileMenu.addItem(.separator())
        fileMenu.addItem(withTitle: "Fechar Janela", action: #selector(NSWindow.performClose(_:)),
                         keyEquivalent: "w")
        fileItem.submenu = fileMenu
        menu.addItem(fileItem)

        let editItem = NSMenuItem()
        let editMenu = NSMenu(title: "Editar")
        editMenu.addItem(withTitle: "Desfazer", action: Selector(("undo:")), keyEquivalent: "z")
        let redo = editMenu.addItem(withTitle: "Refazer", action: Selector(("redo:")), keyEquivalent: "z")
        redo.keyEquivalentModifierMask = [.command, .shift]
        editMenu.addItem(.separator())
        editMenu.addItem(withTitle: "Recortar", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copiar", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Colar", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Selecionar Tudo", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editItem.submenu = editMenu
        menu.addItem(editItem)

        let viewItem = NSMenuItem()
        let viewMenu = NSMenu(title: "Exibir")
        viewMenu.addItem(withTitle: "Recarregar", action: #selector(reload), keyEquivalent: "r").target = self
        viewMenu.addItem(withTitle: "Abrir no Navegador", action: #selector(openBrowser),
                         keyEquivalent: "").target = self
        viewMenu.addItem(withTitle: "Abrir Registro do Aplicativo", action: #selector(openLog),
                         keyEquivalent: "").target = self
        viewItem.submenu = viewMenu
        menu.addItem(viewItem)
        NSApp.mainMenu = menu
    }

    private func createWindow() {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.userContentController.add(self, name: "preferencias")
        configuration.mediaTypesRequiringUserActionForPlayback = []
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.autoresizingMask = [.width, .height]
        webView.allowsBackForwardNavigationGestures = false

        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1160, height: 880),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "Texto em Áudio"
        window.minSize = NSSize(width: 780, height: 600)
        window.contentView = webView
        window.delegate = self
        window.isReleasedWhenClosed = false
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        webView.loadHTMLString("""
            <!doctype html><html lang="pt-BR"><meta charset="utf-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <style>body{font:17px -apple-system,BlinkMacSystemFont,sans-serif;background:#f3f6fa;
            color:#26354a;display:grid;place-content:center;height:90vh;text-align:center}
            h1{font-size:30px;margin-bottom:10px}p{color:#62728a}</style>
            <h1>Texto em Áudio</h1><p>Preparando o aplicativo…</p></html>
            """, baseURL: nil)
    }

    private func launchBackend() {
        do {
            let files = FileManager.default
            for directory in [dataDirectory, outputDirectory, logDirectory] {
                try files.createDirectory(at: directory, withIntermediateDirectories: true)
            }
            if !files.fileExists(atPath: logFile.path) {
                files.createFile(atPath: logFile.path, contents: nil)
            }
            logHandle = try FileHandle(forWritingTo: logFile)
            try logHandle?.seekToEnd()
            if let entry = "\n[\(ISO8601DateFormatter().string(from: Date()))] Iniciando Texto em Áudio\n"
                .data(using: .utf8) {
                try logHandle?.write(contentsOf: entry)
            }
            let directory = files.temporaryDirectory
                .appendingPathComponent("TextoAudio-\(UUID().uuidString)", isDirectory: true)
            try files.createDirectory(at: directory, withIntermediateDirectories: false,
                                      attributes: [.posixPermissions: 0o700])
            stateDirectory = directory
            stateFile = directory.appendingPathComponent("estado.json")

            guard let executables = Bundle.main.executableURL?.deletingLastPathComponent() else {
                throw NSError(domain: "TextoAudio", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "Não foi possível localizar o aplicativo."])
            }
            let executable = executables.appendingPathComponent("TextoAudioBackend")
            guard files.isExecutableFile(atPath: executable.path) else {
                throw NSError(domain: "TextoAudio", code: 2,
                              userInfo: [NSLocalizedDescriptionKey: "O servidor do aplicativo não foi encontrado."])
            }
            let process = Process()
            process.executableURL = executable
            process.arguments = ["--estado", stateFile!.path, "--parent-pid", "\(ProcessInfo.processInfo.processIdentifier)"]
            var environment = ProcessInfo.processInfo.environment
            environment["TEXTO_AUDIO_DATA_DIR"] = dataDirectory.path
            environment["TEXTO_AUDIO_OUTPUT_DIR"] = outputDirectory.path
            environment["PYTHONUNBUFFERED"] = "1"
            process.environment = environment
            process.currentDirectoryURL = Bundle.main.resourceURL ?? executables
            process.standardOutput = logHandle
            process.standardError = logHandle
            process.terminationHandler = { [weak self] _ in
                DispatchQueue.main.async { [weak self] in
                    guard let self = self, !self.shuttingDown, !self.failed else { return }
                    self.showFailure("O servidor local encerrou. Feche e abra o aplicativo para tentar novamente.")
                }
            }
            backend = process
            try process.run()
            readinessDeadline = Date().addingTimeInterval(30)
            readinessTimer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { [weak self] _ in
                MainActor.assumeIsolated { self?.checkReadiness() }
            }
        } catch {
            showFailure(error.localizedDescription)
        }
    }

    private func checkReadiness() {
        guard !shuttingDown, !failed else { return }
        if backend?.isRunning != true {
            showFailure("O servidor local não conseguiu iniciar.")
            return
        }
        if let file = stateFile,
           let data = try? Data(contentsOf: file),
           let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let address = state["url"] as? String,
           let url = URL(string: address),
           url.scheme == "http", url.host == "127.0.0.1", url.port != nil {
            readinessTimer?.invalidate()
            readinessTimer = nil
            serverURL = url
            configurePreferences(for: url)
            webView.load(URLRequest(url: url))
        } else if Date() >= readinessDeadline {
            showFailure("O aplicativo demorou mais que o esperado para iniciar. Consulte o registro para identificar o problema.")
            backend?.terminate()
        }
    }

    /// As portas mudam a cada abertura. Preservamos apenas as opções autorizadas,
    /// nunca o texto, o título ou o conteúdo dos documentos enviados.
    private func configurePreferences(for url: URL) {
        let stored = (try? Data(contentsOf: preferencesFile)).flatMap(validatedPreferences) ?? [:]
        let data = (try? JSONSerialization.data(withJSONObject: stored, options: [.sortedKeys])) ?? Data("{}".utf8)
        let json = String(data: data, encoding: .utf8) ?? "{}"
        let origin = "http://127.0.0.1:\(url.port!)"
        let source = """
            (() => {
              if (location.origin !== '\(origin)') return;
              try {
                const saved = \(json);
                const set = Storage.prototype.setItem;
                set.call(localStorage, 'texto-audio', JSON.stringify(saved));
                Storage.prototype.setItem = function(key, value) {
                  set.call(this, key, value);
                  if (this === localStorage && key === 'texto-audio') {
                    window.webkit.messageHandlers.preferencias.postMessage(String(value));
                  }
                };
              } catch (_) {}
            })();
            """
        let script = WKUserScript(source: source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        webView.configuration.userContentController.addUserScript(script)
    }

    private func validatedPreferences(_ data: Data) -> [String: Any]? {
        guard data.count <= 32_768,
              let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        let keys: Set<String> = ["voz", "velocidade", "pausa", "siglas", "omitir_referencias",
                                 "omitir_numeracao", "normalizar_volume", "pronuncias"]
        guard Set(value.keys).isSubset(of: keys) else { return nil }
        for (key, field) in value {
            switch key {
            case "omitir_referencias", "omitir_numeracao", "normalizar_volume":
                guard let number = field as? NSNumber,
                      CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
            case "velocidade":
                guard let string = field as? String, let number = Int(string), (-50...100).contains(number) else { return nil }
            case "pausa":
                guard let string = field as? String, let number = Int(string), (0...3000).contains(number) else { return nil }
            case "siglas":
                guard let string = field as? String, ["extenso", "letras"].contains(string) else { return nil }
            case "voz":
                guard let string = field as? String, string.count <= 100 else { return nil }
            case "pronuncias":
                guard let string = field as? String, string.count <= 20_000 else { return nil }
            default:
                return nil
            }
        }
        return value
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "preferencias", message.frameInfo.isMainFrame,
              let url = message.frameInfo.request.url, isLocal(url), url.scheme == "http",
              let string = message.body as? String, let data = string.data(using: .utf8),
              let preferences = validatedPreferences(data),
              let canonical = try? JSONSerialization.data(withJSONObject: preferences, options: [.sortedKeys]) else { return }
        try? canonical.write(to: preferencesFile, options: .atomic)
    }

    private func showFailure(_ message: String) {
        guard !failed, !shuttingDown else { return }
        failed = true
        readinessTimer?.invalidate()
        readinessTimer = nil
        let alert = NSAlert()
        alert.alertStyle = .critical
        alert.messageText = "Não foi possível abrir Texto em Áudio"
        alert.informativeText = message
        alert.addButton(withTitle: "Abrir Registro")
        alert.addButton(withTitle: "Fechar")
        alert.beginSheetModal(for: window) { [weak self] response in
            if response == .alertFirstButtonReturn { self?.openLog() }
            NSApp.terminate(nil)
        }
    }

    @objc private func showAbout() {
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "Texto em Áudio",
            .applicationVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "",
            .credits: NSAttributedString(string: "Leitura de textos e documentos em português.\nOs MP3 ficam na pasta Música/Texto em Áudio.")
        ])
    }

    @objc private func openOutputDirectory() {
        NSWorkspace.shared.open(outputDirectory)
    }

    @objc private func openPronunciations() {
        let file = dataDirectory.appendingPathComponent("pronuncias.txt")
        if !FileManager.default.fileExists(atPath: file.path) {
            try? "# Uma pronúncia por linha: palavra = pronúncia\n".write(to: file, atomically: true, encoding: .utf8)
        }
        NSWorkspace.shared.open(file)
    }

    @objc private func openLog() {
        NSWorkspace.shared.open(logFile)
    }

    @objc private func reload() {
        guard let url = serverURL else { return }
        webView.load(URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData))
    }

    @objc private func openBrowser() {
        if let url = serverURL { NSWorkspace.shared.open(url) }
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        return true
    }

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        NSApp.terminate(nil)
        return false
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard !shuttingDown, !failed, backend?.isRunning == true, let url = serverURL else {
            return .terminateNow
        }
        guard !checkingTermination else { return .terminateCancel }
        checkingTermination = true
        var request = URLRequest(url: url.appendingPathComponent("api/info"))
        request.timeoutInterval = 2
        request.cachePolicy = .reloadIgnoringLocalCacheData
        URLSession.shared.dataTask(with: request) { [weak self] data, _, _ in
            let info = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let active = (info?["tarefas_ativas"] as? Int) ?? 0
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { NSApp.reply(toApplicationShouldTerminate: true); return }
                if active > 0 {
                    let alert = NSAlert()
                    alert.messageText = "Há um áudio sendo gerado"
                    alert.informativeText = "Encerrar o aplicativo interromperá a geração. Os MP3 já concluídos continuarão salvos."
                    alert.addButton(withTitle: "Continuar Usando")
                    alert.addButton(withTitle: "Encerrar")
                    alert.beginSheetModal(for: self.window) { response in
                        self.checkingTermination = false
                        NSApp.reply(toApplicationShouldTerminate: response == .alertSecondButtonReturn)
                    }
                } else {
                    self.checkingTermination = false
                    NSApp.reply(toApplicationShouldTerminate: true)
                }
            }
        }.resume()
        return .terminateLater
    }

    func applicationWillTerminate(_ notification: Notification) {
        shuttingDown = true
        webView.configuration.userContentController.removeScriptMessageHandler(forName: "preferencias")
        readinessTimer?.invalidate()
        for download in downloads.values { download.cancel { _ in } }
        for file in downloadStagingFiles.values { try? FileManager.default.removeItem(at: file) }
        if backend?.isRunning == true { backend?.terminate() }
        try? logHandle?.close()
        if let directory = stateDirectory { try? FileManager.default.removeItem(at: directory) }
    }

    private func isLocal(_ url: URL) -> Bool {
        if url.absoluteString == "about:blank" || url.scheme == "blob" { return true }
        guard let server = serverURL else { return false }
        return url.scheme == server.scheme && url.host == server.host && url.port == server.port
    }

    private func openExternal(_ url: URL) {
        if ["http", "https", "mailto"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        guard isLocal(url) else {
            decisionHandler(.cancel)
            openExternal(url)
            return
        }
        if navigationAction.shouldPerformDownload {
            decisionHandler(.download)
        } else if navigationAction.targetFrame == nil {
            decisionHandler(.cancel)
            webView.load(navigationAction.request)
        } else {
            decisionHandler(.allow)
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                 decisionHandler: @escaping @MainActor @Sendable (WKNavigationResponsePolicy) -> Void) {
        guard let url = navigationResponse.response.url, isLocal(url) else {
            decisionHandler(.cancel)
            return
        }
        let disposition = (navigationResponse.response as? HTTPURLResponse)?
            .value(forHTTPHeaderField: "Content-Disposition")?.lowercased() ?? ""
        decisionHandler(disposition.contains("attachment") || !navigationResponse.canShowMIMEType ? .download : .allow)
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        remember(download)
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        remember(download)
    }

    private func remember(_ download: WKDownload) {
        downloads[ObjectIdentifier(download)] = download
        download.delegate = self
    }

    func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                  suggestedFilename: String, completionHandler: @escaping @MainActor @Sendable (URL?) -> Void) {
        let identifier = ObjectIdentifier(download)
        let panel = NSSavePanel()
        panel.title = "Salvar MP3"
        panel.prompt = "Salvar"
        panel.directoryURL = outputDirectory
        panel.nameFieldStringValue = URL(fileURLWithPath: suggestedFilename).lastPathComponent
        panel.canCreateDirectories = true
        panel.beginSheetModal(for: window) { [weak self] result in
            if result == .OK, let destination = panel.url {
                self?.destinations[identifier] = destination
                // WebKit exige um caminho que ainda não exista. Só substituímos
                // o destino confirmado no seletor depois do download concluído.
                let staging = destination.deletingLastPathComponent()
                    .appendingPathComponent(".TextoAudio-\(UUID().uuidString).mp3")
                self?.downloadStagingFiles[identifier] = staging
                completionHandler(staging)
            } else {
                self?.cancelledDownloads.insert(identifier)
                completionHandler(nil)
            }
        }
    }

    func downloadDidFinish(_ download: WKDownload) {
        let identifier = ObjectIdentifier(download)
        if let destination = destinations.removeValue(forKey: identifier),
           let staging = downloadStagingFiles.removeValue(forKey: identifier) {
            do {
                let files = FileManager.default
                if files.fileExists(atPath: destination.path) {
                    _ = try files.replaceItemAt(destination, withItemAt: staging)
                } else {
                    try files.moveItem(at: staging, to: destination)
                }
                NSWorkspace.shared.activateFileViewerSelecting([destination])
            } catch {
                try? FileManager.default.removeItem(at: staging)
                showDownloadError(error)
            }
        }
        downloads.removeValue(forKey: identifier)
        cancelledDownloads.remove(identifier)
    }

    func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
        let identifier = ObjectIdentifier(download)
        let wasCancelled = cancelledDownloads.remove(identifier) != nil
        downloads.removeValue(forKey: identifier)
        destinations.removeValue(forKey: identifier)
        if let staging = downloadStagingFiles.removeValue(forKey: identifier) {
            try? FileManager.default.removeItem(at: staging)
        }
        guard !wasCancelled, !shuttingDown, (error as NSError).code != NSURLErrorCancelled else { return }
        showDownloadError(error)
    }

    private func showDownloadError(_ error: Error) {
        let alert = NSAlert()
        alert.messageText = "Não foi possível salvar o MP3"
        alert.informativeText = error.localizedDescription
        alert.addButton(withTitle: "OK")
        alert.beginSheetModal(for: window)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor @Sendable ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.title = "Selecionar Documento"
        panel.prompt = "Abrir"
        panel.canChooseFiles = true
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.allowedContentTypes = [.plainText, .pdf, UTType(filenameExtension: "docx")].compactMap { $0 }
        panel.beginSheetModal(for: window) { response in
            completionHandler(response == .OK ? panel.urls : nil)
        }
    }

    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor @Sendable () -> Void) {
        let alert = NSAlert()
        alert.messageText = "Texto em Áudio"
        alert.informativeText = message
        alert.addButton(withTitle: "OK")
        alert.beginSheetModal(for: window) { _ in completionHandler() }
    }

    func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor @Sendable (Bool) -> Void) {
        let alert = NSAlert()
        alert.messageText = "Texto em Áudio"
        alert.informativeText = message
        alert.addButton(withTitle: "Confirmar")
        alert.addButton(withTitle: "Cancelar")
        alert.beginSheetModal(for: window) { response in
            completionHandler(response == .alertFirstButtonReturn)
        }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        if !shuttingDown { reload() }
    }
}

MainActor.assumeIsolated {
    let application = NSApplication.shared
    let delegate = TextoAudioApp()
    application.setActivationPolicy(.regular)
    application.delegate = delegate
    withExtendedLifetime(delegate) { application.run() }
}
