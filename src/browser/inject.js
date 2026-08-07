(() => {
    const config = FINGERPRINT_CONFIG;
    
    // Override navigator properties
    Object.defineProperties(navigator, {
        userAgent: { value: config.navigator.userAgent },
        platform: { value: config.navigator.platform },
        hardwareConcurrency: { value: config.navigator.hardwareConcurrency },
        deviceMemory: { value: config.navigator.deviceMemory },
        languages: { value: [config.navigator.language] },
        language: { value: config.navigator.language }
    });

    // Override screen properties
    Object.defineProperties(screen, {
        width: { value: config.screen.width },
        height: { value: config.screen.height },
        availWidth: { value: config.screen.availWidth },
        availHeight: { value: config.screen.availHeight },
        colorDepth: { value: config.screen.colorDepth },
        pixelDepth: { value: config.screen.pixelDepth }
    });

    // WebRTC protection
    if (config.webrtc === 'Disable') {
        delete window.RTCPeerConnection;
        delete window.RTCDataChannel;
        delete window.RTCSessionDescription;
        delete window.RTCIceCandidate;
    }

    // Canvas fingerprint protection
    if (config.canvas_fp) {
        const originalGetContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, attributes) {
            const context = originalGetContext.call(this, type, attributes);
            if (context && (type === '2d' || type === 'webgl' || type === 'webgl2')) {
                const originalToDataURL = context.canvas.toDataURL;
                context.canvas.toDataURL = function() {
                    return originalToDataURL.apply(this, arguments)
                        .replace(/./g, (c) => String.fromCharCode(c.charCodeAt(0) + Math.random() * 10 - 5));
                }
            }
            return context;
        }
    }

    // WebGL fingerprint protection
    if (config.webgl_fp) {
        const getParameterProxyHandler = {
            apply: function(target, thisArg, argumentsList) {
                const param = argumentsList[0];
                if (param === 37445) { // UNMASKED_VENDOR_WEBGL
                    return 'Intel Inc.';
                }
                if (param === 37446) { // UNMASKED_RENDERER_WEBGL
                    return 'Intel Iris OpenGL Engine';
                }
                return target.apply(thisArg, argumentsList);
            }
        };
        
        const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = new Proxy(originalGetParameter, getParameterProxyHandler);
    }

    // AudioContext fingerprint protection
    if (config.audio_fp) {
        const originalGetChannelData = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = function(channel) {
            const array = originalGetChannelData.call(this, channel);
            for(let i = 0; i < array.length; i += 100) {
                array[i] = array[i] + (Math.random() * 0.0001 - 0.00005);
            }
            return array;
        }
    }

    // Client Rects fingerprint protection
    if (config.client_rects_fp) {
        const originalGetClientRects = Element.prototype.getClientRects;
        Element.prototype.getClientRects = function() {
            const rects = originalGetClientRects.call(this);
            for (let i = 0; i < rects.length; i++) {
                rects[i].top += Math.random() * 0.01;
                rects[i].left += Math.random() * 0.01;
            }
            return rects;
        }
    }
})();
