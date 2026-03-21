const { divide } = require('./app');

test('divide by zero throws', () => {
    expect(() => divide(10, 0)).toThrow();
});

test('divide normal', () => {
    expect(divide(10, 2)).toBe(5);
});
