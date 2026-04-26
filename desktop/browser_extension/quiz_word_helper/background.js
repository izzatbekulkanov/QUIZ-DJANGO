function normalizeBridgeBaseUrl(rawValue) {
  return String(rawValue || "").trim().replace(/\/+$/, "");
}

async function proxyBridgeRequest(message) {
  const bridgeBaseUrl = normalizeBridgeBaseUrl(message.bridgeBaseUrl || "http://127.0.0.1:8765");
  if (!bridgeBaseUrl) {
    return {
      ok: false,
      status: 0,
      error: "Word yordamchisi manzili topilmadi.",
    };
  }

  const requestHeaders = Object.assign({}, message.headers || {});
  let body = null;

  if (message.body !== undefined && message.body !== null) {
    if (typeof message.body === "string") {
      body = message.body;
    } else {
      body = JSON.stringify(message.body);
      if (!requestHeaders["Content-Type"]) {
        requestHeaders["Content-Type"] = "application/json";
      }
    }
  }

  try {
    const response = await fetch(`${bridgeBaseUrl}${message.path || ""}`, {
      method: message.method || "GET",
      headers: requestHeaders,
      body,
    });
    const text = await response.text();

    let json = null;
    try {
      json = text ? JSON.parse(text) : null;
    } catch (error) {
      json = null;
    }

    return {
      ok: response.ok,
      status: response.status,
      data: json,
      text,
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      error: error?.message || "Word yordamchisiga ulanishda xatolik yuz berdi.",
    };
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "QUIZ_WORD_HELPER_FETCH") {
    return false;
  }

  proxyBridgeRequest(message)
    .then((payload) => sendResponse(payload))
    .catch((error) =>
      sendResponse({
        ok: false,
        status: 0,
        error: error?.message || "Word yordamchisini tekshirishda xatolik yuz berdi.",
      })
    );

  return true;
});
