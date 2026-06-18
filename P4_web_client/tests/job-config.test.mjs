import test from "node:test";
import assert from "node:assert/strict";

import {
  getModuleJobConfig,
  isModuleJob,
  MODULE_JOB_SCHEMAS,
} from "../src/job-config.js";

test("module job config exposes pack and unpack defaults", () => {
  assert.equal(isModuleJob("pack_modules"), true);
  assert.equal(isModuleJob("unpack_modules"), true);
  assert.equal(isModuleJob("generate_pdf"), false);

  assert.deepEqual(getModuleJobConfig("pack_modules"), {
    title: "Pack modules",
    submitLabel: "Pack",
    defaultLabel: "pack modules",
  });
});

test("schema list includes legacy module schemas", () => {
  assert.equal(MODULE_JOB_SCHEMAS.length >= 6, true);
  assert.deepEqual(MODULE_JOB_SCHEMAS[0], ["proced.xsd", "proced.xsd"]);
});
