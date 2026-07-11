/**
 * Formats a UTC ISO timestamp to the user's local timezone.
 * Automatically adapts to any timezone — works for India, US, UAE, anywhere.
 * 
 * @param isoString - UTC ISO string e.g. "2026-07-11T04:30:00Z"
 * @param format - "datetime" | "date" | "time" | "relative"
 */
export function formatDateTime(
    isoString: string | null | undefined,
    format: "datetime" | "date" | "time" | "relative" = "datetime"
): string {
    if (!isoString) return "—";
    
    // Normalize timezone-less UTC ISO strings (e.g. from Python native datetime serialization)
    let formattedString = isoString.trim();
    if (
        formattedString && 
        !formattedString.endsWith("Z") && 
        !formattedString.includes("+") && 
        !/-\d{2}:\d{2}$/.test(formattedString)
    ) {
        // If it looks like "YYYY-MM-DDTHH:MM:SS" or similar, append "Z" for UTC parsing
        formattedString = formattedString + "Z";
    }
    
    const date = new Date(formattedString);
    if (isNaN(date.getTime())) return "—";
    
    const userLocale = typeof navigator !== "undefined" ? (navigator.language || "en-IN") : "en-IN";
    const userTimezone = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
    
    switch (format) {
        case "datetime":
            return date.toLocaleString(userLocale, {
                timeZone: userTimezone,
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                hour12: true
            });
        
        case "date":
            return date.toLocaleDateString(userLocale, {
                timeZone: userTimezone,
                day: "2-digit",
                month: "short",
                year: "numeric"
            });
        
        case "time":
            return date.toLocaleTimeString(userLocale, {
                timeZone: userTimezone,
                hour: "2-digit",
                minute: "2-digit",
                hour12: true
            });
        
        case "relative": {
            const now = new Date();
            const diffMs = now.getTime() - date.getTime();
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMins / 60);
            const diffDays = Math.floor(diffHours / 24);
            
            if (diffMins < 1) return "just now";
            if (diffMins < 60) return `${diffMins}m ago`;
            if (diffHours < 24) return `${diffHours}h ago`;
            if (diffDays < 7) return `${diffDays}d ago`;
            return formatDateTime(isoString, "date");
        }
        
        default:
            return date.toLocaleString();
    }
}
