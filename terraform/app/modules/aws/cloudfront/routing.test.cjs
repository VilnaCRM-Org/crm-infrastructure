const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');

const context = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, 'routing.js'), 'utf8'), context);

test('SPA navigation serves the shell for GET and HEAD', () => {
    for (const method of ['GET', 'HEAD']) {
        for (const uri of ['/', '/sign-in', '/sign-up/', '/password-recovery', '/unknown/nested-route']) {
            const request = { method, uri, querystring: { next: { value: '/sign-up' } }, headers: {} };
            const querystring = request.querystring;
            assert.equal(context.handler({ request }), request);
            assert.equal(request.uri, '/index.html');
            assert.equal(request.querystring, querystring);
        }
    }
});

test('assets and API endpoints are never rewritten, including extensionless keys', () => {
    for (const uri of [
        '/index.html', '/app-config.js', '/favicon.ico', '/missing.js', '/missing.css',
        '/static/js/main.hash.js', '/static/extensionless', '/assets/icon', '/assets',
        '/api', '/api/users', '/graphql', '/graphql/query', '/.well-known/security.txt',
        '/%61pi/users', '/%61ssets/icon', '/missing%2Ejs', '/invalid%escape',
    ]) {
        const request = { method: 'GET', uri };
        assert.equal(context.handler({ request }).uri, uri);
    }
});

test('prefix lookalikes remain valid SPA routes', () => {
    for (const uri of ['/api-settings', '/static-page', '/assets-manager']) {
        assert.equal(context.handler({ request: { method: 'GET', uri } }).uri, '/index.html');
    }
});

test('non-navigation methods remain unchanged', () => {
    for (const method of ['POST', 'PUT', 'DELETE', 'OPTIONS']) {
        assert.equal(context.handler({ request: { method, uri: '/sign-in' } }).uri, '/sign-in');
    }
});
