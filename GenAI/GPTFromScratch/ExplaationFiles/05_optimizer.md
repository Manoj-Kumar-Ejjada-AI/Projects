> **How does the model actually change its parameters?**

That's exactly what this line does.

```python
# create a PyTorch optimizer
optimizer = torch.optim.AdamW(m.parameters(), lr=1e-3)
```

Let's understand it from the ground up.

---

# First, what is an optimizer?

Suppose you're teaching a student.

The student answers

```text
Question:
What comes after "I"?

Student:
Apple ❌
```

You tell him

```text
Wrong.

Correct answer is "am".
```

Now think.

How does the student's brain improve?

There must be **something** inside the brain that says

```text
"I made a mistake.

I'll remember this.

I'll change my knowledge slightly."
```

That "something" is exactly what an **optimizer** is for a neural network.

---

# Recall what our model contains

When we created the model

```python
m = BigramLanguageModel(vocab_size)
```

Inside `__init__()`, we had

```python
self.token_embedding_table = nn.Embedding(vocab_size, vocab_size)
```

Suppose

```text
vocab_size = 65
```

PyTorch secretly created

```text
65 × 65

=

4225 numbers
```

Something like

```
0.12
-0.81
0.45
...
4225 random numbers
```

These numbers are called

* Parameters
* Weights
* Learnable values

These are **the model's memory**.

---

# Where are these parameters?

Imagine the embedding table.

```
                Next Token Scores
          ---------------------------------
Token 0 →  0.2   -1.4   2.3  ... 65 values
Token 1 → -0.8    0.4   1.1  ...
Token 2 →  2.1   -0.6   0.9  ...
...
Token64 → ...
```

Every number inside this table is a parameter.

This entire table is what the model learns.

---

# What does `m.parameters()` do?

Now look at

```python
m.parameters()
```

This simply tells PyTorch

> "Give me every trainable number inside this model."

Imagine opening the model.

```
Model
│
├── Embedding Table
│
├── Weight 1
├── Weight 2
├── Weight 3
│
...
│
└── Weight 4225
```

`m.parameters()` returns all of them.

Think of it as

```text
Model

↓

List all trainable parameters

↓

[weight1,
 weight2,
 weight3,
 ...
 weight4225]
```

Nothing changes yet.

We're only collecting them.

---

# Why does the optimizer need these parameters?

Remember

After

```python
loss.backward()
```

every parameter gets a gradient.

Suppose

```
Weight

2.35
```

Gradient

```
+0.12
```

Another

```
Weight

-1.82
```

Gradient

```
-0.08
```

Now someone has to actually change these weights.

Who does that?

The optimizer.

---

Think of it like this.

```
Parameters

↓

Gradients

↓

Optimizer

↓

Updated Parameters
```

Without an optimizer,

the gradients would simply sit there.

Nothing would learn.

---

# Why not update them ourselves?

Imagine we write

```python
weight = weight - 0.001 * gradient
```

That would work!

In fact,

that's the basic Gradient Descent algorithm.

The optimizer automates this for **every parameter**.

Imagine

```
4225 parameters
```

Would you like to manually update all of them?

Of course not.

PyTorch does it.

---

# Now let's understand this part

```python
torch.optim.AdamW(...)
```

This is the optimizer algorithm.

Think of it as

```text
Teacher
```

There are many teaching styles.

For example

Teacher A

```
Very slow
```

Teacher B

```
Very aggressive
```

Teacher C

```
Adjusts based on student's mistakes
```

Different optimizers update parameters differently.

---

Some popular optimizers

```
Gradient Descent
```

↓

Very basic

---

```
SGD
```

↓

Faster

---

```
Momentum
```

↓

Remembers previous direction

---

```
Adam
```

↓

Very smart

---

```
AdamW
```

↓

Improved version of Adam

````

Karpathy uses

```python
AdamW
````

because it's one of the best general-purpose optimizers for Transformers.

---

# What is Adam?

Don't worry about the math yet.

Think of climbing a mountain.

Suppose you're blindfolded.

Your goal is to reach the bottom.

Every step,

someone tells you

```
Go left
```

You move left.

Next time

```
Go left again
```

Next

```
Go slightly left
```

Eventually

you reach the valley.

Adam does something similar.

Instead of taking fixed steps,

it adjusts

* how big the step should be
* how confident it is
* how fast it should move

That's why it usually learns much faster than simple gradient descent.

---

# What is AdamW?

AdamW is almost Adam,

but it also keeps weights from growing too large.

Imagine a student.

Without discipline,

the student's notebook becomes messy.

AdamW occasionally says

```
Let's keep everything neat.
```

Technically,

it performs something called

**Weight Decay**

which helps prevent overfitting.

You don't need to worry about the math right now.

Just remember

```
AdamW

=

Adam

+

Weight Decay
```

---

# What is `lr`?

```python
lr=1e-3
```

This is one of the most important hyperparameters.

First,

what does

```python
1e-3
```

mean?

Python notation

```
1e3

=

1000
```

```
1e2

=

100
```

```
1e1

=

10
```

```
1e-1

=

0.1
```

```
1e-2

=

0.01
```

```
1e-3

=

0.001
```

So

```python
lr=1e-3
```

means

```python
learning_rate = 0.001
```

---

# What is the learning rate?

Imagine learning to play cricket.

Suppose your coach says

```
Your stance is wrong.
```

You have two choices.

Option 1

Move a tiny bit.

```
🙂
```

Option 2

Jump five feet sideways.

```
😄
```

Which is better?

Usually

small improvements.

That's exactly what the learning rate controls.

---

Small learning rate

```
0.0001
```

↓

Tiny improvements

↓

Very stable

↓

Slow learning

---

Large learning rate

```
1
```

↓

Huge jumps

↓

Very fast

↓

Can overshoot the solution

---

Medium

```
0.001
```

↓

Usually a good balance.

---

# Visualizing learning rate

Imagine the loss surface.

```
Loss

 ^
 |
 |         *
 |       *
 |     *
 |   *
 | *
 +------------------------>
```

Goal

Reach the bottom.

Small learning rate

```
o

 o

  o

   o

    o
```

Slow but safe.

Large learning rate

```
o

      o

           o

    o

            o
```

Keeps jumping around.

May never settle.

---

# Now let's connect everything

When you later execute

```python
loss.backward()
```

PyTorch computes

```
Gradient of every parameter
```

For example

| Parameter | Current Value | Gradient |
| --------- | ------------: | -------: |
| W1        |          0.80 |    +0.20 |
| W2        |         -1.50 |    -0.05 |
| W3        |          2.30 |    +0.10 |

The optimizer now uses these gradients.

With

```python
optimizer.step()
```

the parameters become approximately

| Parameter |   Old |      New |
| --------- | ----: | -------: |
| W1        |  0.80 |   0.7998 |
| W2        | -1.50 | -1.49995 |
| W3        |  2.30 |   2.2999 |

Notice something:

The changes are **very tiny** because the learning rate is `0.001`.

One update doesn't make the model intelligent.

But after **thousands of updates**, these tiny changes accumulate, and the random embedding table gradually becomes a meaningful lookup table for predicting the next token.

---

# The complete picture

Here's the entire learning pipeline you've now covered:

```text
              Create Model
                    │
                    ▼
        Random Parameters (4225 numbers)
                    │
                    ▼
      optimizer = AdamW(m.parameters(), lr=0.001)
                    │
                    ▼
             Get Training Batch
                    │
                    ▼
              Forward Pass
                    │
                    ▼
             Compute Loss
                    │
                    ▼
            loss.backward()
      (Compute gradients for all parameters)
                    │
                    ▼
           optimizer.step()
      (Update all 4225 parameters slightly)
                    │
                    ▼
         Model becomes a little better
                    │
                    ▼
              Repeat thousands of times
```

## One important insight

Notice that **the optimizer never makes predictions**. It never sees text directly.

Its only job is:

1. Look at the gradients computed by `loss.backward()`.
2. Update every trainable parameter returned by `m.parameters()`.
3. Repeat this after every batch.

So you can think of the responsibilities like this:

* **Model (`forward`)** → Makes predictions.
* **Loss function (`cross_entropy`)** → Measures how wrong those predictions are.
* **Autograd (`backward`)** → Computes how each parameter contributed to the error.
* **Optimizer (`AdamW`)** → Uses those gradients to improve the parameters.

This separation of responsibilities is one of the core design ideas in PyTorch, and you'll see the same pattern in almost every deep learning project you work on.
