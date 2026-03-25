import type { SlashCommand } from '../types'

/**
 * Parse the plain-text response from the `/commands` gateway command
 * into a structured list of slash commands.
 *
 * Expected format:
 *   ℹ️ Slash commands
 *
 *   Session
 *     /new  - Start a new session.
 *     /reset  - Reset the current session.
 *
 *   Options
 *     /think <level> (/thinking, /t) - Set thinking level.
 */
export function parseCommandsResponse(text: string): SlashCommand[] {
  const commands: SlashCommand[] = []
  const lines = text.split('\n')

  // Match lines like:  /name  - Description
  // Also handles:      /name <arg> (/alias1, /alias2) - Description
  const cmdRegex = /^\s*(\/\S+)(?:\s+<[^>]+>)?(?:\s+\([^)]+\))?\s+-\s+(.+)$/

  for (const line of lines) {
    const match = line.match(cmdRegex)
    if (match) {
      commands.push({
        name: match[1],
        description: match[2].trim(),
      })
    }
  }

  return commands
}
