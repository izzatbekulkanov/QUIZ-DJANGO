(function () {
  const PAGE_SOURCE = "quiz-word-helper-page";
  const EXTENSION_SOURCE = "quiz-word-helper-extension";

  window.addEventListener("message", (event) => {
    if (event.source !== window) {
      return;
    }

    const payload = event.data || {};
    if (payload.source !== PAGE_SOURCE) {
      return;
    }

    if (payload.type === "QUIZ_WORD_HELPER_PING") {
      window.postMessage(
        {
          source: EXTENSION_SOURCE,
          type: "QUIZ_WORD_HELPER_PONG",
          ok: true,
        },
        "*"
      );
      return;
    }

    if (payload.type !== "QUIZ_WORD_HELPER_REQUEST") {
      return;
    }

    chrome.runtime.sendMessage(
      {
        type: "QUIZ_WORD_HELPER_FETCH",
        bridgeBaseUrl: payload.bridgeBaseUrl,
        path: payload.path,
        method: payload.method,
        headers: payload.headers,
        body: payload.body,
      },
      (response) => {
        const runtimeError = chrome.runtime.lastError;
        window.postMessage(
          {
            source: EXTENSION_SOURCE,
            type: "QUIZ_WORD_HELPER_RESPONSE",
            requestId: payload.requestId,
            ok: !runtimeError && !!response?.ok,
            status: response?.status || 0,
            data: response?.data || null,
            text: response?.text || "",
            error:
              runtimeError?.message ||
              response?.error ||
              "Word yordamchisi bilan ulanishda xatolik yuz berdi.",
          },
          "*"
        );
      }
    );
  });
})();
