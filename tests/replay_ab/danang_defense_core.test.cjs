const test=require("node:test"),assert=require("node:assert/strict");
const core=require("../../frontend/danang_defense_core.js");
test("seek selects the latest sampled frame at or before time",()=>{const f=[{t:5},{t:10},{t:15}];assert.equal(core.frameIndexAt(f,4),0);assert.equal(core.frameIndexAt(f,12),1);assert.equal(core.frameIndexAt(f,99),2)});
test("representative change preserves worse and better signs",()=>{assert.equal(core.representativeChange(100,80),-20);assert.equal(core.representativeChange(100,150),50)});
test("phase labels distinguish green and clearance",()=>{assert.match(core.phaseLabel(0),/green/);assert.equal(core.phaseLabel(1),"clearance")});
