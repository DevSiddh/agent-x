// syn_js_001 — buggy: no zero-division guard
// Fix: add if (b === 0) throw new Error('Division by zero')
function divide(a, b) {
    return a / b;
}

module.exports = { divide };
