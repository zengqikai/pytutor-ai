"""误区专项练习 API — 为 M1-M8 每类误区提供靶向练习"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db

router = APIRouter()

MC_EXERCISES = [
    {"code":"M1","type":"fix","title":"if 条件中的 = 和 ==","desc":"修复代码：if x = 10 应该改为 if x == 10","starter":"x = 10\nif x = 10:\n    print('x is ten')","solution":"x = 10\nif x == 10:\n    print('x is ten')","input":"","output":"x is ten\n","hint":"if 后面用 == 比较，不是 = 赋值"},
    {"code":"M1","type":"fix","title":"判断满分","desc":"修复 score = 100 的比较错误","starter":"score = 90\nif score = 100:\n    print('满分')","solution":"score = 90\nif score == 100:\n    print('满分')","input":"","output":"","hint":"= 是赋值，== 才是比较"},
    {"code":"M2","type":"fix","title":"修复缩进错误","desc":"for 循环体需要缩进","starter":"for i in range(3):\nprint(i)","solution":"for i in range(3):\n    print(i)","input":"","output":"0\n1\n2\n","hint":"for 后面的代码需要缩进 4 个空格"},
    {"code":"M2","type":"fix","title":"if 代码块缩进","desc":"if 后面的 print 需要缩进","starter":"age=20\nif age>=18:\nprint('adult')","solution":"age=20\nif age>=18:\n    print('adult')","input":"","output":"adult\n","hint":"if 后面的代码块需要缩进"},
    {"code":"M3","type":"fix","title":"append 返回值误解","desc":"修复：new=numbers.append(4) 之后打印的是 None","starter":"numbers=[1,2,3]\nnew=numbers.append(4)\nprint(new)","solution":"numbers=[1,2,3]\nnumbers.append(4)\nprint(numbers)","input":"","output":"[1, 2, 3, 4]\n","hint":"append 直接修改原列表，不返回新列表"},
    {"code":"M3","type":"fix","title":"sort 返回值","desc":"修复 sort 返回 None 的问题","starter":"nums=[3,1,2]\nresult=nums.sort()\nprint(result)","solution":"nums=[3,1,2]\nnums.sort()\nprint(nums)","input":"","output":"[1, 2, 3]\n","hint":"sort() 返回 None，应该打印原列表"},
    {"code":"M4","type":"fix","title":"for 循环中的索引混淆","desc":"修复：for i in list 中的 i 是元素不是索引","starter":"fruits=['a','b','c']\nfor i in fruits:\n    print(fruits[i])","solution":"fruits=['a','b','c']\nfor f in fruits:\n    print(f)","input":"","output":"a\nb\nc\n","hint":"for i in list 中的 i 就是元素本身，直接用"},
    {"code":"M4","type":"fix","title":"打印列表元素","desc":"修复：用正确的变量名替代索引访问","starter":"items=[10,20,30]\nfor x in range(3):\n    print(items[x])","solution":"items=[10,20,30]\nfor item in items:\n    print(item)","input":"","output":"10\n20\n30\n","hint":"直接 for item in items 更简洁"},
    {"code":"M5","type":"fix","title":"打印 1 到 5","desc":"修改 range 让它包含 5","starter":"for i in range(1,5):\n    print(i)","solution":"for i in range(1,6):\n    print(i)","input":"","output":"1\n2\n3\n4\n5\n","hint":"range(1,6) 才包含 5，结束值要 +1"},
    {"code":"M5","type":"fix","title":"range 开始值","desc":"从 0 开始打印到 4","starter":"for i in range(0,4):\n    print(i)","solution":"for i in range(0,5):\n    print(i)","input":"","output":"0\n1\n2\n3\n4\n","hint":"要包含 4，range 写 range(0,5)"},
    {"code":"M6","type":"fix","title":"函数用 return 而非 print","desc":"修复函数让它返回计算结果","starter":"def add(a,b):\n    print(a+b)\n\nr=add(3,5)\nprint(r)","solution":"def add(a,b):\n    return a+b\n\nr=add(3,5)\nprint(r)","input":"","output":"8\n","hint":"return 把结果交回，print 只是显示"},
    {"code":"M6","type":"fix","title":"return 和 print 顺序","desc":"return 后面的代码不会执行","starter":"def double(x):\n    print('calculating')\n    return x*2\n    print('done')","solution":"def double(x):\n    print('calculating')\n    result = x*2\n    print('done')\n    return result","input":"","output":"calculating\ndone\n","hint":"return 之后的代码不会执行"},
    {"code":"M7","type":"fix","title":"字符串拼接数字","desc":"修复 TypeError：不能 str + int","starter":"age=20\nprint('I am '+age)","solution":"age=20\nprint('I am '+str(age))","input":"","output":"I am 20\n","hint":"用 str() 把数字转成字符串"},
    {"code":"M7","type":"fix","title":"input 得到的字符串","desc":"修复：input 返回字符串，不能直接计算","starter":"x=input('num: ')\nprint(x+10)","solution":"x=input('num: ')\nprint(int(x)+10)","input":"5","output":"15\n","hint":"input 返回字符串，需要 int() 转换"},
    {"code":"M8","type":"fix","title":"while 循环变量更新","desc":"修复死循环：count 没有增加","starter":"count=0\nwhile count<5:\n    print(count)","solution":"count=0\nwhile count<5:\n    print(count)\n    count=count+1","input":"","output":"0\n1\n2\n3\n4\n","hint":"循环内需要 count=count+1 更新变量"},
    {"code":"M8","type":"fix","title":"while 条件边界","desc":"修复：应该打印 5 到 1","starter":"n=5\nwhile n>=0:\n    print(n)\n    n=n-1","solution":"n=5\nwhile n>=1:\n    print(n)\n    n=n-1","input":"","output":"5\n4\n3\n2\n1\n","hint":"条件是 n>=1 还是 n>=0？检查是否多打印了 0"},
]


@router.post("/seed-mc-exercises")
async def seed_mc_exercises(db: AsyncSession = Depends(get_db)):
    """将 M1-M8 误区专项练习写入数据库（幂等）。"""
    from app.models.exercise import Exercise, TestCase

    count = 0
    for ex in MC_EXERCISES:
        # 检查是否已存在
        from sqlalchemy import select as sa_select, func
        existing = await db.execute(
            sa_select(func.count()).select_from(Exercise).where(Exercise.title == ex["title"])
        )
        if existing.scalar() > 0:
            continue

        exercise = Exercise(
            title=f'[{ex["code"]}] {ex["title"]}',
            description=ex["desc"],
            difficulty=1,
            concepts=ex["code"],
            example_input=ex.get("input", ""),
            example_output=ex.get("output", ""),
            reference_solution=ex.get("solution", ""),
            learning_objective=ex.get("hint", ""),
        )
        db.add(exercise)
        await db.flush()

        if ex.get("output"):
            tc = TestCase(
                exercise_id=exercise.id,
                description=f"{ex['code']} 测试",
                input_data=ex.get("input", ""),
                expected_output=ex.get("output", ""),
                order_index=0,
                is_hidden=False,
            )
            db.add(tc)

        count += 1

    await db.commit()
    return {"seeded": count, "total": len(MC_EXERCISES)}
