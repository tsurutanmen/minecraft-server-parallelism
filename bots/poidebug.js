const mineflayer = require('mineflayer')
const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: 'poitest', version: '26.1', auth: 'offline' })
const w = (ms) => new Promise((r) => setTimeout(r, ms))
let last = ''
bot.on('messagestr', (m) => { last = m })
async function ask(cmd, ms = 800) { last = ''; bot.chat(cmd); await w(ms); return last }
bot.once('spawn', async () => {
  await w(1500); bot.chat('/gamemode creative @s'); await w(400)
  bot.chat('/tp @s 3000 200 3000'); await w(8000)
  bot.chat('/summon minecraft:villager ~ ~ ~2'); await w(3000)
  console.log('AGE', await ask('/data get entity @e[type=minecraft:villager,limit=1,sort=nearest] Age'))
  console.log('TIME', await ask('/time query daytime'), await ask('/time query gametime'))
  console.log('SETBLOCK', await ask('/setblock ~3 ~ ~3 minecraft:composter'))
  console.log('BELOW', await ask('/execute if block ~3 ~-1 ~3 minecraft:air'))
  for (let i = 0; i < 4; i++) {
    await w(10000)
    const mem = await ask('/data get entity @e[type=minecraft:villager,limit=1,sort=nearest] Brain.memories', 1200)
    const vd = await ask('/data get entity @e[type=minecraft:villager,limit=1,sort=nearest] VillagerData', 1000)
    const pos = await ask('/data get entity @e[type=minecraft:villager,limit=1,sort=nearest] Pos', 1000)
    console.log(`t=${(i + 1) * 10}s`, vd.slice(0, 160), '|', pos.slice(0, 120), '|', mem.slice(0, 500))
  }
  process.exit(0)
})
setTimeout(() => process.exit(3), 200000)
