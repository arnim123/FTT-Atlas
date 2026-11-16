import { writeFile } from 'node:fs/promises';

export const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

export class BrowserSession {
  constructor(socket) {
    this.socket = socket;
    this.sequence = 0;
    this.pending = new Map();
    this.errors = [];
    socket.addEventListener('message', event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const waiter = this.pending.get(message.id);
        this.pending.delete(message.id);
        if (message.error) waiter?.reject(new Error(message.error.message));
        else waiter?.resolve(message.result);
      }
      if (message.method === 'Runtime.exceptionThrown') this.errors.push(message.params.exceptionDetails.exception?.description ?? message.params.exceptionDetails.text);
      if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') this.errors.push(message.params.args.map(arg => arg.value ?? arg.description).join(' '));
    });
  }

  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
    const session = new BrowserSession(socket);
    await session.send('Runtime.enable');
    await session.send('Page.enable');
    return session;
  }

  send(method, params = {}) {
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); reject(new Error(`CDP timed out: ${method}`)); }, 15_000);
      this.pending.set(id, { resolve: result => { clearTimeout(timer); resolve(result); }, reject: error => { clearTimeout(timer); reject(error); } });
      this.socket.send(JSON.stringify({ id, method, params }));
    });
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
    return result.result.value;
  }

  async wait(expression, message = expression, timeout = 10_000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      if (await this.evaluate(expression)) return;
      await pause(80);
    }
    throw new Error(`Timed out waiting for ${message}`);
  }

  async ready() { await this.wait(`!document.querySelector('[aria-label^="Loading"], [aria-label="Searching documents"]')`, 'screen loading to finish'); }

  async route(path) {
    await this.evaluate(`history.pushState(null, '', ${JSON.stringify(path)}); window.dispatchEvent(new PopStateEvent('popstate'));`);
    await pause(50);
    await this.ready();
  }

  async clickExpression(expression) {
    await this.wait(`Boolean(${expression})`, 'click target');
    const rect = await this.evaluate(`(() => { const element = ${expression}; element.scrollIntoView({ block: 'center', inline: 'center' }); const rect = element.getBoundingClientRect(); return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, width: rect.width, height: rect.height }; })()`);
    if (!rect.width || !rect.height) throw new Error(`Click target is hidden: ${expression}`);
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: rect.x, y: rect.y });
    await this.send('Input.dispatchMouseEvent', { type: 'mousePressed', x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
    await this.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: rect.x, y: rect.y, button: 'left', clickCount: 1 });
  }

  click(selector) { return this.clickExpression(`[...document.querySelectorAll(${JSON.stringify(selector)})].find(element => element.getClientRects().length)`); }

  clickText(text, selector = 'button') { return this.clickExpression(`[...document.querySelectorAll(${JSON.stringify(selector)})].find(element => element.getClientRects().length && element.textContent.trim() === ${JSON.stringify(text)})`); }

  async value(selector, value) {
    await this.wait(`Boolean(document.querySelector(${JSON.stringify(selector)}))`, selector);
    await this.evaluate(`(() => { const element = document.querySelector(${JSON.stringify(selector)}); const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value').set; setter.call(element, ${JSON.stringify(value)}); element.dispatchEvent(new Event('input', { bubbles: true })); element.dispatchEvent(new Event('change', { bubbles: true })); })()`);
  }

  async key(key, code, modifiers = 0) {
    await this.send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, modifiers });
    await this.send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers });
  }

  async screenshot(path) {
    const result = await this.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(path, Buffer.from(result.data, 'base64'));
  }

  async viewport(width, height) { await this.send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false }); }
  close() { this.socket.close(); }
}
