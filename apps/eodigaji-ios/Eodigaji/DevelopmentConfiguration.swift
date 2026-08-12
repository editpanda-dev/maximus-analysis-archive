import Foundation

public enum DevelopmentConfiguration {
    public static let defaultAPIBaseURL = URL(string: "http://127.0.0.1:8000")!
    public static let apiBaseURLEnvironmentKey = "EODIGAJI_API_BASE_URL"

    /// A debug-only environment override keeps the API host out of the UI.
    public static var apiBaseURL: URL {
#if DEBUG
        if let value = ProcessInfo.processInfo.environment[apiBaseURLEnvironmentKey],
           let url = URL(string: value),
           url.scheme != nil,
           url.host != nil {
            return url
        }
#endif
        return defaultAPIBaseURL
    }
}
