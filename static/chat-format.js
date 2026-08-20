/* Message formatting for the table chat.
 *
 * A trimmed port of board2's chat markdown (frontend/src/pages/home/chat-state.js).
 * Kept: the inline grammar, the code fence, the link safety check, the bare-URL
 * linkifier and the bounded render cache. Left behind: channels, raffles, polls,
 * attachments, personas, pins, moderation and the Telegram bridge -- a poker
 * room needs a line of text with emphasis in it, not a message bus.
 *
 * The spoiler is a plain click-to-reveal here rather than board2's animated
 * character scramble: that needs a requestAnimationFrame registry mutating every
 * hidden character, and this table already has a render loop to feed.
 *
 * Order matters and is the whole safety argument: the text is escaped first, and
 * every tag below is introduced afterwards from literals. Nothing a player types
 * can become markup.
 */
(() => {
  "use strict";

  const NULL = String.fromCharCode(0);
  const CACHE = new Map();
  const CACHE_LIMIT = 300;

  const escapeHtml = value => String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#039;");

  function isSafeLinkUrl(rawUrl) {
    if (!rawUrl || rawUrl.length > 1024) return false;
    const lower = rawUrl.toLowerCase();
    return lower.startsWith("http://") || lower.startsWith("https://")
      || lower.startsWith("mailto:") || lower.startsWith("tel:");
  }

  function linkify(escapedHtml) {
    if (!escapedHtml) return escapedHtml;
    return escapedHtml.replace(/(^|[\s>(])(https?:\/\/[^\s<"']+)/g, (_match, lead, urlRaw) => {
      // A full stop or bracket right after a URL belongs to the sentence, not
      // to the address.
      const trailingMatch = urlRaw.match(/[).,!?;:]+$/);
      const trailing = trailingMatch ? trailingMatch[0] : "";
      const url = trailing ? urlRaw.slice(0, -trailing.length) : urlRaw;
      return `${lead}<a class="p8-chat-link" href="${url}" target="_blank" rel="noopener noreferrer nofollow">${url}</a>${trailing}`;
    });
  }

  function inline(plainText) {
    let escaped = escapeHtml(plainText);
    const tokens = [];
    // Code and links are parked as placeholders so the emphasis rules below
    // cannot reach inside them -- an asterisk in a URL is an asterisk.
    const park = html => {
      tokens.push(html);
      return `${NULL}MD${tokens.length - 1}${NULL}`;
    };

    escaped = escaped.replace(/`([^`\n]+)`/g, (_m, code) => park(`<code class="p8-chat-code">${code}</code>`));
    escaped = escaped.replace(/\|\|([\s\S]+?)\|\|/g, (_m, inner) =>
      park(`<span class="p8-chat-spoiler" data-chat-spoiler tabindex="0" role="button" aria-label="Показать скрытый текст">${inner}</span>`));
    escaped = escaped.replace(/~~([\s\S]+?)~~/g, "<s>$1</s>");
    escaped = escaped.replace(/\*\*([^*][\s\S]*?)\*\*/g, "<strong>$1</strong>");
    escaped = escaped.replace(/__([^_][\s\S]*?)__/g, "<strong>$1</strong>");
    escaped = escaped.replace(/(^|[^*\w])\*([^*\s][\s\S]*?[^*\s]|[^*\s])\*(?!\*)/g, "$1<em>$2</em>");
    escaped = escaped.replace(/(^|[^_\w])_([^_\s][\s\S]*?[^_\s]|[^_\s])_(?!_)/g, "$1<em>$2</em>");
    escaped = escaped.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (match, text, url) => {
      if (!isSafeLinkUrl(url)) return match;
      const safeUrl = url.replace(/&/g, "&amp;").replace(/"/g, "&quot;")
        .replace(/</g, "&lt;").replace(/>/g, "&gt;");
      return park(`<a class="p8-chat-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer nofollow">${text}</a>`);
    });

    // Built by concatenation, not a template literal: the backslash in \d
    // does not survive one, and the pattern quietly matches the letter d.
    escaped = escaped.replace(new RegExp(NULL + "MD([0-9]+)" + NULL, "g"), (_m, idx) => tokens[Number(idx)] || "");
    return linkify(escaped);
  }

  function renderUncached(text) {
    const source = String(text == null ? "" : text);
    if (!source) return "";
    const html = [];
    let i = 0;
    while (i < source.length) {
      const fence = source.indexOf("```", i);
      if (fence < 0) {
        html.push(inline(source.slice(i)).replace(/\n/g, "<br>"));
        break;
      }
      if (fence > i) html.push(inline(source.slice(i, fence)).replace(/\n/g, "<br>"));
      const close = source.indexOf("```", fence + 3);
      if (close < 0) {
        // An unclosed fence is somebody still typing, not a code block.
        html.push(inline(source.slice(fence)).replace(/\n/g, "<br>"));
        break;
      }
      let block = source.slice(fence + 3, close);
      if (block.startsWith("\n")) block = block.slice(1);
      if (block.endsWith("\n")) block = block.slice(0, -1);
      html.push(`<pre class="p8-chat-block"><code>${escapeHtml(block)}</code></pre>`);
      i = close + 3;
    }
    return html.join("");
  }

  // The feed is redrawn whole on every snapshot, so the same lines are
  // re-tokenised constantly. Bounded, oldest-out, keyed on the raw text.
  function render(text) {
    if (text == null || text === "") return "";
    const key = String(text);
    const cached = CACHE.get(key);
    if (cached !== undefined) return cached;
    const rendered = renderUncached(key);
    if (CACHE.size >= CACHE_LIMIT) CACHE.delete(CACHE.keys().next().value);
    CACHE.set(key, rendered);
    return rendered;
  }

  /** Wrap the input's selection in a pair of markers, or drop the pair in empty. */
  function wrapSelection(input, before, after = before) {
    if (!input) return;
    const start = input.selectionStart ?? input.value.length;
    const end = input.selectionEnd ?? start;
    const selected = input.value.slice(start, end);
    input.value = input.value.slice(0, start) + before + selected + after + input.value.slice(end);
    input.focus();
    const caret = start + before.length;
    input.setSelectionRange(caret, caret + selected.length);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  window.Poker8ChatFormat = { render, escapeHtml, wrapSelection };
})();
