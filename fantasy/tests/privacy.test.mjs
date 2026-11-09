import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';

test('public Fantasy HQ PR never includes private Flaim staging exports',()=>{
  assert.equal(existsSync('fantasy/flaim-staging'),false,
    'Private league exports must not be committed to the public GitHub Pages repository');
});
